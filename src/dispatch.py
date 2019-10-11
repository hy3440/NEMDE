import offer
import datetime
import gurobipy
import interconnect
import logging
import result


# def enable_fcas(fcas, unit):
#     if fcas is None:
#         return False
#     if fcas.bid_type == 'RAISEREG' or fcas.bid_type == 'LOWERREG':
#         if unit.agc_status == 0:
#             return False
#     if fcas.max_avail <= 0:
#         return False
#     if sum(fcas.band_avail) <= 0:
#         return False
#     if fcas.enablement_max < 0:
#         return False
#     if unit.energy is not None:
#         if unit.energy.max_avail < fcas.enablement_min:
#             return False
#     if unit.initial_mw < fcas.enablement_min:
#         return False
#     if unit.initial_mw > fcas.enablement_max:
#         return False
#     fcas.enablement_status = 1
#     return True


def dispatch(start, i, process, fcas_flag=False, losses_flag=False, fixed_interflow_flag=False, fixed_target_flag=False):
    try:
        intervals = 30 if process == 'predispatch' else 5
        t = start + i * datetime.timedelta(minutes=intervals)
        model = gurobipy.Model('nemde')
        obj = 0
        regions, interconnectors = interconnect.get_regions_and_interconnectors(t, start, i, process)

        # for region_id, region in regions.items():
        #     print('{}: {}'.format(region_id, region.total_demand))

        for ic_id, ic in interconnectors.items():
            regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
            regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
            ic.mw_flow = model.addVar(lb=-ic.import_limit, ub=ic.export_limit)
            regions[ic.region_to].net_mw_flow += ic.mw_flow
            regions[ic.region_from].net_mw_flow -= ic.mw_flow

            # Fixed inter-flow
            if fixed_interflow_flag:
                model.addConstr(ic.mw_flow == ic.mw_flow_record)

        # Calculate inter-region losses
        if losses_flag:
            # links = interconnect.init_links()
            # offer.add_mnsp_bids(links, t)
            # for name, link in links.items():
            #     link.offer = [model.addVar(lb=0.0, ub=avail) for avail in link.band_avail]
            #     if name == 'BLNKVIC':
            #         link.mw_flow = model.addVar(lb=0, ub=link.max_cap, name=name)
            #         model.addConstr(link.mw_flow == sum(link.offer))
            #     else:
            #         link.mw_flow = model.addVar(lb=-link.max_cap, ub=0, name=name)
            #         model.addConstr(link.mw_flow == -sum(link.offer))
            #     link.cost = sum([o * p for o, p in zip(link.offer, link.price_band)])
            #     # Add cost to objective
            #     obj += link.cost
            interconnect.calculate_interconnector_losses(model, regions, interconnectors)

        units = offer.get_units(t, fcas_flag, start, i, process)
        # units = offer.get_units(t, fcas_flag)
        for unit in units.values():
            # Unit participates in the energy market
            if unit.energy is not None:
                # Dispatch target at each price band
                unit.offers = [model.addVar(ub=avail) for avail in unit.energy.band_avail]
                # Total dispatch total_cleared
                unit.total_cleared = model.addVar(name='Total_Cleared_{}'.format(unit.duid))
                # # Unit max cap
                # if unit.max_capacity is not None:
                #     model.addConstr(unit.total_cleared <= unit.max_capacity)
                #     if unit.total_cleared_record > unit.max_capacity:
                #         logging.warning('{} {} total cleared record {} exceed max cap {}.'.format(unit.dispatch_type,
                #                                                                                   unit.duid,
                #                                                                                   unit.total_cleared_record,
                #                                                                                   unit.max_cap))
                # # Unit energy bid max avail
                # if unit.total_cleared_record > unit.energy.max_avail:
                #     logging.warning('{} {} total cleared record {} exceed max avail {}.'.format(unit.dispatch_type,
                #                                                                                 unit.duid,
                #                                                                                 unit.total_cleared_record,
                #                                                                                 unit.energy.max_avail))
                # if fixed_target_flag:
                #     model.addConstr(unit.total_cleared == unit.total_cleared_record)
                model.addConstr(unit.total_cleared == sum(unit.offers), 'TOTAL_CLEARED_{}'.format(unit.duid))
                # Unconstrained Intermittent Generation Forecasts (UIGF) for Dispatch
                if unit.forecast is not None:
                    regions[unit.region_id].available_generation += unit.forecast
                    model.addConstr(unit.total_cleared <= unit.forecast, 'FORECAST_{}'.format(unit.duid))
                # # Raise constraint
                # model.addConstr(unit.total_cleared <= unit.initial_mw + intervals * unit.energy.roc_up, 'ROC_UP_{}'.format(unit.duid))
                # # Lower constraint
                # model.addConstr(unit.total_cleared >= unit.initial_mw - intervals * unit.energy.roc_down, 'ROC_DOWN_{}'.format(unit.duid))
                # Marginal loss factor
                if unit.transmission_loss_factor is None:
                    logging.warning('{} {} has no MLF.'.format(unit.dispatch_type, unit.duid))
                    unit.transmission_loss_factor = 1.0
                # Cost of an unit
                unit.cost = sum([g * (p / unit.transmission_loss_factor) for g, p in zip(unit.offers, unit.energy.price_band)])
                if unit.dispatch_type == 'GENERATOR':
                    # Add cost to objective
                    obj += unit.cost
                    # Add generation to region generation
                    regions[unit.region_id].dispatchable_generation += unit.total_cleared
                    if unit.forecast is None:
                        regions[unit.region_id].available_generation += unit.energy.max_avail
                elif unit.dispatch_type == 'LOAD':
                    # Minus cost from objective
                    obj -= unit.cost
                    # Add load to region load
                    regions[unit.region_id].dispatchable_load_temp += unit.total_cleared
                    regions[unit.region_id].available_load += unit.energy.max_avail
                else:
                    logging.error('{} has no dispatch type.'.format(unit.duid))
                # Fixed loading
                if unit.energy.fixed_load != 0:
                    model.addConstr(unit.total_cleared == unit.energy.fixed_load, 'FIXED_LOAD_{}'.format(unit.duid))

            # # Unit is registered for FCAS only
            # else:
            #     unit.total_cleared = 0
            # if unit.fcas_bids != {} and fcas_flag:
            #     print('FCAS Warning!!!!!!!!!!!!!!!!!!!')
            #     for fcas in unit.fcas_bids.values():
            #         # Scale for UIGF
            #         if unit.forecast is not None:
            #             fcas.high_breakpoint = fcas.high_breakpoint - (
            #                     fcas.enablement_max - min(fcas.enablement_max, unit.forecast))
            #             fcas.enablement_max = min(fcas.enablement_max, unit.forecast)
            #         # Scale for AGC
            #         # if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
            #         if enable_fcas(fcas, unit):
            #             fcas.value = model.addVar(ub=fcas.max_avail, name='{}_{}'.format(fcas.bid_type, unit.duid))
            #             fcas.lower_slope_coeff = (fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
            #             fcas.upper_slope_coeff = (fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
            #     for bid_type, fcas in unit.fcas_bids.items():
            #         if fcas.enablement_status == 1:
            #             fcas.offers = [model.addVar(ub=avail) for avail in fcas.band_avail]
            #             model.addConstr(fcas.value == sum(fcas.offers))
            #             obj += sum([g * p for g, p in zip(fcas.offers, fcas.price_band)])
            #             if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
            #                 # # Joint ramping constraint
            #                 # if unit.energy is not None and bid_type == 'RAISEREG' and unit.scada_ramp_up_rate > 0:
            #                 #     model.addConstr(unit.total_cleared + fcas.value <= unit.initial_mw + 5 * unit.scada_ramp_up_rate)
            #                 # elif unit.energy is not None and bid_type == 'LOWERREG' and unit.scada_ramp_down_rate > 0:
            #                 #     model.addConstr(unit.total_cleared - fcas.value >= unit.initial_mw - 5 * unit.scada_ramp_down_rate)
            #
            #                 # Energy and regulating FCAS capacity constraint
            #                 model.addConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value <= fcas.enablement_max)
            #                 model.addConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value >= fcas.enablement_min)
            #             else:
            #                 # Joint capacity constraint
            #                 if 'RAISEREG' in unit.fcas_bids:
            #                     raisereg = unit.fcas_bids['RAISEREG']
            #                     model.addConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value + raisereg.enablement_status * raisereg.value <= fcas.enablement_max)
            #                 if 'LOWERREG' in unit.fcas_bids:
            #                     lowerreg = unit.fcas_bids['LOWERREG']
            #                     model.addConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value - lowerreg.enablement_status * lowerreg.value >= fcas.enablement_min)
            #             # # FCAS availability #1
            #             # model.addConstr(fcas.value <= fcas.max_avail)
            #             # # FCAS availability #2
            #             # if fcas.upper_slope_coeff != 0:
            #             #     model.addConstr(fcas.value <= (fcas.enablement_max - unit.total_cleared) / fcas.upper_slope_coeff)
            #             # # FCAS availability #3
            #             # if fcas.lower_slope_coeff != 0:
            #             #     model.addConstr(fcas.value <= (unit.total_cleared - fcas.enablement_min) / fcas.lower_slope_coeff)
            #             # if bid_type == 'RAISEREG':
            #             #     # FCAS availability #4
            #             #     for contigency_type in {'RAISE6SEC', 'RAISE60SEC', 'RAISE5MIN'}:
            #             #         if contigency_type in unit.fcas_bids:
            #             #             contigency = unit.fcas_bids[contigency_type]
            #             #             model.addConstr(fcas.value <= contigency.enablement_max - unit.total_cleared - (contigency.upper_slope_coeff * contigency.value))
            #             #     # FCAS availability #5
            #             #     # joint_ramp_raise_max = unit.initial_mw + (unit.agc_ramp_rate * 5)
            #             #     # model.addConstr(fcas.value <= joint_ramp_raise_max - unit.total_cleared)
            #             # elif bid_type == 'LOWERREG':
            #             #     # FCAS availability #4
            #             #     for contigency_type in {'LOWER6SEC', 'LOWER60SEC', 'LOWER5MIN'}:
            #             #         if contigency_type in unit.fcas_bids:
            #             #             contigency = unit.fcas_bids[contigency_type]
            #             #             model.addConstr(fcas.value <= unit.total_cleared - contigency.enablement_min - (contigency.lower_slope_coeff * contigency.value))
            #             #     # FCAS availability #5
            #             #     # joint_ramp_lower_min = unit.initial_mw - (unit.agc_ramp_down_rate * 5)
            #             #     # model.addConstr(fcas.value <= unit.total_cleared - joint_ramp_lower_min)
            #             # elif bid_type[:5] == 'RAISE':
            #             #     # FCAS availability #4
            #             #     if fcas.upper_slope_coeff != 0 and 'RAISEREG' in unit.fcas_bids:
            #             #         model.addConstr(fcas.value <= (fcas.enablement_max - unit.total_cleared - unit.fcas_bids['RAISEREG'].value) / fcas.upper_slope_coeff)
            #             # elif bid_type[:5] == 'LOWER':
            #             #     # FCAS availability #4
            #             #     if fcas.lower_slope_coeff != 0 and 'LOWERREG' in unit.fcas_bids:
            #         #     #         model.addConstr(fcas.value <= (unit.total_cleared - fcas.enablement_min - unit.fcas_bids['LOWERREG'].value) / fcas.lower_slope_coeff)
            #         # if unit.region is None:
            #         #     logging.warning('{} has no region'.format(unit.duid))
            #         # else:
            #         #     regions[unit.region].fcas_local_dispatch[bid_type] += fcas.value
        # Regional balance constraint
        for region in regions.values():
            region.dispatchable_load = model.addVar(ub=region.available_load, name='Load_{}'.format(region.region_id))
            model.addConstr(region.dispatchable_load == region.dispatchable_load_temp)
            model.addConstr(region.dispatchable_generation + region.net_mw_flow == region.total_demand + region.dispatchable_load + region.losses, region.region_id)
            # for bid_type, value in region.fcas_local_dispatch.items():
            #     model.addConstr(value == region.fcas_local_dispatch_record[bid_type], '{}_{}'.format(region.region_id, bid_type))
        # Set objective
        model.setObjective(obj, gurobipy.GRB.MINIMIZE)

        # Optimize model
        model.optimize()
        # print('isMIP: {}'.format(model.isMIP))

        # do IIS
        print('The model is infeasible; computing IIS')
        model.computeIIS()
        print('\nThe following constraint(s) cannot be satisfied:')
        for c in model.getConstrs():
            if c.IISConstr:
                print('%s' % c.constrName)

        # Get dual total_cleared of regional energy balance constraint
        for constr in model.getConstrs():
            if constr.constrName in regions:
                regions[constr.constrName].rrp = constr.pi
                print(constr.pi)
            # else:
            #     l = constr.constrName.split('_')
            #     if l[0] in regions:
            #         regions[l[0]].fcas_rrp[l[1]] = constr.pi

        # for name, link in links.items():
        #     print('{}: {}, {}'.format(name, link.mw_flow.x, link.losses.x))

        # Generate result csv
        # result.generate_result_csv(fixed_interflow_flag, fixed_target_flag, t, model.objVal, obj_record, interconnectors, regions, units)
        # test.test_negative_bids(generators)
        if process == 'dispatch':
            result.generate_dispatchis(t, regions)
        elif process == 'predispatch':
            result.generate_predispatchis(start, t, i, regions)
        else:
            result.generate_p5min(start, t, regions)
        result.generate_dispatchload(units, t, start, process)

    except gurobipy.GurobiError as e:
         print('Error code ' + str(e.errno) + ": " + str(e))

    # except AttributeError:
    #     print('Encountered an attribute error')


if __name__ == '__main__':
    logging.basicConfig(filename='nemde.log', filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)
    # dispatch(False, False, True, False)  # Fixed inter-flow
    # dispatch(False, False, False, True)  # Fixed unit target
    start = datetime.datetime(2019, 7, 19, 4, 5, 0)
    process = 'dispatch'
    for i in range(288):
        dispatch(start, i, process, losses_flag=False)
