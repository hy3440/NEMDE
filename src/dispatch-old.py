import constrain
import datetime
import gurobipy
import json
import interconnect
import logging
import offer
import result
import preprocess


def condition1(process, i):
    """ All intervals of dispatch and first i of p5min and predispatch.

    Args:
        process (str): 'dispatch', 'p5min' or 'predispatch'
        i (int): Interval number

    Returns:
        bool: True if satisfied; False otherwise.
    """
    return process == 'dispatch' or i == 0


def condition2(process, i):
    """ All intervals of dispatch, first i of p5min, and none of predispatch.

        Args:
            process (str): 'dispatch', 'p5min' or 'predispatch'
            i (int): Interval number

        Returns:
            bool: True if satisfied; False otherwise.
        """
    return process == 'dispatch' or (process == 'p5min' and i == 0)


def condition3(process, dis, pre, rhs):
    c1 = (process == 'p5min' or process == 'predispatch') and pre
    c2 = process == 'dispatch' and dis
    c3 = rhs is not None
    return (c1 or c2) and c3


def enable_fcas(fcas, unit, process, i):
    if fcas is None:
        return False
    # For Dispatch and 1st interval of Predispatch and 5min Predispatch, regulating FCAS is enabled if AGC status is On
    if condition1(process, i):
        if fcas.bid_type == 'RAISEREG' or fcas.bid_type == 'LOWERREG':
            if unit.agc_status == 0:
                return False
    # The maximum availability offered for the service is greater than zero.
    if fcas.max_avail <= 0:
        return False
    # At least one of the offer price bands has a capacity greater than zero for the service
    if sum(fcas.band_avail) <= 0:
        return False
    # The energy availability is greater than or equal to the FCAS trapezium enablement minimum of the service
    if unit.energy is not None:
        if unit.energy.max_avail < fcas.enablement_min:
            return False
    # The FCAS trapezium enablement maximum of the service is greater than or equal to zero
    if fcas.enablement_max < 0:
        return False
    # The unit is initially operating between the FCAS trapezium enablement minimum and maximum of the service
    if unit.initial_mw < fcas.enablement_min:
        # logging.debug('{} {} initial {} < min {}'.format(unit.duid, fcas.bid_type, unit.initial_mw, fcas.enablement_min))
        fcas.flag = 4
        return False
    if unit.initial_mw > fcas.enablement_max:
        # logging.debug('{} {} initial {} > max {}'.format(unit.duid, fcas.bid_type, unit.initial_mw, fcas.enablement_max))
        fcas.flag = 4
        return False
    fcas.enablement_status = 1
    fcas.flag = 1
    return True


def dispatch(cvp, start, i, process,
             hard_flag=True,  # Apply hard constraints
             fcas_flag=True,  # Calculate FCAS
             constr_flag=True,  # Apply generic constraints
             losses_flag=True,  # Calculate losses
             fixed_interflow_flag=False,  # Fix interflow
             fixed_target_flag=False,  # Fix generator target
             link_flag=False,  # Calculate links
             dual_flag=False,  # Calculate dual var as price
             ic_record_flag=False  # Apply interconnector import/export limit record
             ):
    try:
        intervals = 30 if process == 'predispatch' else 5
        # Calculate current interval (or period) datetime
        current = start + i * datetime.timedelta(minutes=intervals)
        logging.info('----------------------------------------------------------------------------------')
        logging.info('Current interval is {} (No. {} starting at {}) for {}'.format(current, i, start, process))
        model = gurobipy.Model('nemde')
        cost, penalty = 0, 0
        slack_variables = set()

        # Get market price cap (MPC) and floor
        voll, market_price_floor = constrain.get_market_price(current)

        # Get regions, interconnectors, and case solution
        regions, interconnectors, solution, links = interconnect.get_regions_and_interconnectors(current, start, i, process, fcas_flag, link_flag)

        for ic_id, ic in interconnectors.items():
            # Define interconnector MW flow
            ic.mw_flow = model.addVar(lb=-gurobipy.GRB.INFINITY, name='Mw_Flow_{}'.format(ic_id))

            # Interconnector Capacity Limit constraint (lower bound)
            ic.flow_deficit = model.addVar(name='Flow_Deficit_{}'.format(ic_id))  # Item5
            slack_variables.add('Flow_Deficit_{}'.format(ic_id))
            if hard_flag:
                model.addConstr(ic.flow_deficit == 0, 'FLOW_DEFICIT_{}'.format(ic_id))
            penalty += ic.flow_deficit * cvp['Interconnector_Capacity_Limit'] * voll
            ic.import_limit_constr = model.addConstr(ic.mw_flow + ic.flow_deficit >= -ic.import_limit, 'IMPORT_LIMIT_{}'.format(ic_id))
            if ic.mw_flow_record is not None and ic.mw_flow_record < -ic.import_limit and abs(ic.mw_flow_record + ic.import_limit) > 1:
                logging.warning('IC {} mw flow record {} below import limit {}'.format(ic_id, ic.mw_flow_record, -ic.import_limit))

            # Interconnector Capacity Limit constraint (upper bound)
            ic.flow_surplus = model.addVar(name='Flow_Surplus_{}'.format(ic_id))  # Item5
            slack_variables.add('Flow_Surplus_{}'.format(ic_id))
            if hard_flag:
                model.addConstr(ic.flow_surplus == 0, 'FLOW_SURPLUS_{}'.format(ic_id))
            penalty += ic.flow_surplus * cvp['Interconnector_Capacity_Limit'] * voll
            ic.export_limit_constr = model.addConstr(ic.mw_flow - ic.flow_surplus <= ic.export_limit, 'EXPORT_LIMIT_{}'.format(ic_id))
            if ic.mw_flow_record is not None and ic.mw_flow_record > ic.export_limit and abs(ic.mw_flow_record - ic.export_limit) > 1:
                logging.warning('IC {} mw flow record {} above export limit {}'.format(ic_id, ic.mw_flow_record, ic.export_limit))

            if ic_record_flag:
                # Interconnector Import Limit Record
                ic.import_record_constr = model.addConstr(ic.mw_flow >= ic.import_limit_record, 'IMPORT_LIMIT_RECORD_{}'.format(ic_id))
                if ic.mw_flow_record is not None and ic.import_limit_record is not None and ic.mw_flow_record < ic.import_limit_record and abs(ic.mw_flow_record - ic.import_limit_record) > 1:
                    logging.warning('IC {} mw flow record {} below import limit record {}'.format(ic_id, ic.mw_flow_record, ic.import_limit_record))
                # Interconnector Export Limit Record
                ic.export_record_constr = model.addConstr(ic.mw_flow <= ic.export_limit_record, 'EXPORT_LIMIT_RECORD_{}'.format(ic_id))
                if ic.mw_flow_record is not None and ic.export_limit_record is not None and ic.mw_flow_record > ic.export_limit_record and abs(ic.mw_flow_record - ic.export_limit_record) > 1:
                    logging.warning('IC {} mw flow record {} above export limit {}'.format(ic_id, ic.mw_flow_record, ic.export_limit_record))

            # Allocate inter-flow to regions
            if not link_flag or (link_flag and ic_id != 'T-V-MNSP1'):
                regions[ic.region_to].net_mw_flow_record += ic.mw_flow_record
                regions[ic.region_from].net_mw_flow_record -= ic.mw_flow_record
                regions[ic.region_to].net_mw_flow += ic.mw_flow
                regions[ic.region_from].net_mw_flow -= ic.mw_flow

            # Fixed inter-flow
            if fixed_interflow_flag:
                model.addConstr(ic.mw_flow == ic.mw_flow_record, 'FIXED_INTERFLOW_{}'.format(ic_id))

        if link_flag:
            for link_id, link in links.items():
                # Avail at each price band
                link.offers = [model.addVar(ub=avail, name='Avail{}_{}'.format(no, link_id)) for no, avail in enumerate(link.band_avail)]
                # Link flow
                link.mw_flow = model.addVar(name='Link_Flow_{}'.format(link_id))

                # MNSPInterconnector ramp rate constraint (Up)
                if link.ramp_up_rate is not None:
                    link.mnsp_up_deficit = model.addVar(name='MNSP_Up_Deficit_{}'.format(link_id))  # Item4
                    slack_variables.add('MNSP_Up_Deficit_{}'.format(link_id))  # CONFUSED
                    if hard_flag:
                        model.addConstr(link.mnsp_up_deficit == 0, 'MNSP_UP_DEFICIT_{}'.format(link_id))
                    penalty += link.mnsp_up_deficit * cvp['MNSPInterconnector_Ramp_Rate'] * voll
                    link.mnsp_up_constr = model.addConstr(link.mw_flow - link.mnsp_up_deficit <= link.metered_mw_flow + intervals * link.ramp_up_rate / 60, 'MNSPINTERCONNECTOR_UP_RAMP_RATE_{}'.format(link_id))
                    if link.mw_flow_record is not None and link.mw_flow_record > link.metered_mw_flow + intervals * link.ramp_up_rate / 60:
                        logging.warning('Link {} above MNSPInterconnector up ramp rate constraint'.format(link_id))
                        logging.debug(f'MW flow {link.mw_flow_record} metered {link.metered_mw_flow} up rate {link.ramp_up_rate/60}')

                # MNSPInterconnector ramp rate constraint (Down)
                if link.ramp_up_rate is not None:
                    link.mnsp_dn_surplus = model.addVar(name='MNSP_Dn_Surplus_{}'.format(link_id))  # Item4
                    slack_variables.add('MNSP_Dn_Surplus_{}'.format(link_id))  # CONFUSED
                    if hard_flag:
                        model.addConstr(link.mnsp_dn_surplus == 0, 'MNSP_DN_SURPLUS_{}'.format(link_id))
                    penalty += link.mnsp_dn_surplus * cvp['MNSPInterconnector_Ramp_Rate'] * voll
                    link.mnsp_dn_constr = model.addConstr(link.mw_flow + link.mnsp_dn_surplus >= link.metered_mw_flow - intervals * link.ramp_up_rate / 60, 'MNSPINTERCONNECTOR_DN_RAMP_RATE'.format(link_id))
                    if link.mw_flow_record is not None and link.mw_flow_record < link.metered_mw_flow - intervals * link.ramp_up_rate / 60:
                        logging.warning('Link {} below MNSPInterconnector down ramp rate constraint'.format(link_id))

                # Total Band MW Offer constraint - MNSP only
                link.mnsp_offer_deficit = model.addVar(name='MNSP_Offer_Deficit_{}'.format(link_id))  # Item9
                slack_variables.add('MNSP_Offer_Deficit'.format(link_id))
                if hard_flag:
                    model.addConstr(link.mnsp_offer_deficit == 0, 'MNSP_OFFER_DEFICIT_{}'.format(link_id))
                penalty += link.mnsp_offer_deficit * cvp['Total_Band_MW_Offer-MNSP'] * voll
                link.total_band_mw_offer_constr = model.addConstr(link.mw_flow + link.mnsp_offer_deficit == sum(link.offers), 'MNSP_TOTAL_BAND_MW_OFFER_{}'.format(link_id))

                # MNSP Max Capacity
                if link.max_capacity is not None:
                    if link.mw_flow_record is not None and link.mw_flow_record > link.max_capacity:
                        logging.warning('Link {} mw flow record {} above max capacity {}'.format(link_id, link.mw_flow_record, link.max_capacity))

                # MNSP Availability constraint
                if link.max_avail is not None:
                    link.mnsp_capacity_deficit = model.addVar(name='MNSP_Capacity_Deficit_{}'.format(link_id))  # Item15
                    slack_variables.add('MNSP_Capacity_Deficit'.format(link_id))  # CONFUSED
                    if hard_flag:
                        model.addConstr(link.mnsp_capacity_deficit == 0, 'MNSP_CAPACITY_DEFICIT_{}'.format(link_id))
                    penalty += link.mnsp_capacity_deficit * cvp['MNSP_Availability'] * voll
                    link.mnsp_availability_constr = model.addConstr(link.mw_flow - link.mnsp_capacity_deficit <= link.max_avail, 'MNSP_AVAILABILITY_{}'.format(link_id))
                    if link.mw_flow_record is not None and link.mw_flow_record > link.max_avail:
                        logging.warning('Link {} mw flow record {} above max avail {}'.format(link_id, link.mw_flow_record, link.max_avail))

                link.from_cost = sum([o * (p / link.from_region_tlf) for o, p in zip(link.offers, link.price_band)])
                link.to_cost = sum([o * (p / link.to_region_tlf) for o, p in zip(link.offers, link.price_band)])
                # Add cost to objective
                cost -= link.from_cost  # As load for from_region
                cost += link.to_cost  # As generator for to_region

                regions[link.from_region].net_mw_flow += link.mw_flow
                regions[link.to_region].net_mw_flow -= link.mw_flow
                regions[link.from_region].net_mw_flow_record += link.mw_flow_record
                regions[link.to_region].net_mw_flow_record -= link.mw_flow_record

            model.addConstr(interconnectors['T-V-MNSP1'].mw_flow == links['BLNKTAS'].mw_flow - links['BLNKVIC'].mw_flow)
            model.addSOS(gurobipy.GRB.SOS_TYPE1, [links['BLNKTAS'].mw_flow, links['BLNKVIC'].mw_flow])

        # Calculate inter-region losses
        if losses_flag:
            interconnect.sos_calculate_interconnector_losses(model, regions, interconnectors)

        units, connection_points = offer.get_units(current, start, i, process, fcas_flag)
        for unit in units.values():
            # Unit participates in the energy market
            if unit.energy is not None:
                # Dispatch target at each price band
                unit.offers = [model.addVar(ub=avail, name='Avail{}_{}'.format(no, unit.duid)) for no, avail in enumerate(unit.energy.band_avail)]
                # Total dispatch total_cleared
                unit.total_cleared = model.addVar(name='Total_Cleared_{}'.format(unit.duid))
                # Unit max cap
                if unit.max_capacity is not None:
                    # model.addConstr(unit.total_cleared <= unit.max_capacity, 'MAX_CAPACITY_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.max_capacity:
                        logging.warning('{} {} total cleared record {} above max capacity {}'.format(unit.dispatch_type, unit.duid, unit.total_cleared_record, unit.max_capacity))
                # Unit energy bid max avail
                if unit.energy.max_avail is not None:
                    if unit.dispatch_type == 'LOAD':
                        unit.deficit_trader_energy_capacity = model.addVar(name='Deficit_Trader_Energy_Capacity_{}'.format(unit.duid))  # Item14 CONFUSED
                        slack_variables.add('Deficit_Trader_Energy_Capacity_{}'.format(unit.duid))
                        if hard_flag:
                            model.addConstr(unit.deficit_trader_energy_capacity == 0, 'DEFICIT_TRADER_ENERGY_CAPACITY_{}'.format(unit.duid))
                        penalty += unit.deficit_trader_energy_capacity * cvp['Unit_MaxAvail'] * voll
                        unit.max_avail_constr = model.addConstr(unit.total_cleared - unit.deficit_trader_energy_capacity <= unit.energy.max_avail, 'MAX_AVAIL_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.energy.max_avail:
                        logging.warning('{} {} total cleared record {} above max avail {}'.format(unit.dispatch_type, unit.duid, unit.total_cleared_record, unit.energy.max_avail))
                # Custom flag for testing code
                if fixed_target_flag:
                    model.addConstr(unit.total_cleared == unit.total_cleared_record, 'FIXED_TARGET_{}'.format(unit.duid))

                # Total Band MW Offer constraint
                unit.deficit_offer_mw = model.addVar(name='Deficit_Offer_MW_{}'.format(unit.duid))  # Item8
                slack_variables.add('Deficit_Offer_MW_{}'.format(unit.duid))
                if hard_flag:
                    model.addConstr(unit.deficit_offer_mw == 0, 'DEFICIT_OFFER_MW_{}'.format(unit.duid))
                penalty += unit.deficit_offer_mw * cvp['Total_Band_MW_Offer'] * voll
                unit.total_band_mw_offer_constr = model.addConstr(unit.total_cleared + unit.deficit_offer_mw == sum(unit.offers), 'TOTAL_BAND_MW_OFFER_{}'.format(unit.duid))
                
                # Unconstrained Intermittent Generation Forecasts (UIGF) for Dispatch
                if unit.forecast_priority is not None and unit.forecast_poe50 is None:
                    logging.error('Generator {} forecast priority is but has no forecast POE50'.format(unit.duid))
                elif unit.forecast_poe50 is not None:
                    regions[unit.region_id].available_generation += unit.forecast_poe50
                    unit.uigf_surplus = model.addVar(name='UIGF_Surplus_{}'.format(unit.duid))  # Item12
                    slack_variables.add('UIGF_Surplus_{}'.format(unit.duid))
                    if hard_flag:
                        model.addConstr(unit.uigf_surplus == 0, 'UIGF_SURPLUS_{}'.format(unit.duid))
                    penalty += unit.uigf_surplus * cvp['UIGF'] * voll
                    model.addConstr(unit.total_cleared - unit.uigf_surplus <= unit.forecast_poe50, 'UIGF_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record > unit.forecast_poe50:
                        logging.warning('{} {} total cleared record {} above UIGF forecast {}'.format(unit.dispatch_type, unit.duid, unit.total_cleared_record, unit.forecast_poe50))

                # Unit Ramp Rate constraint (Raise)
                up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
                unit.surplus_ramp_rate = model.addVar(name='Surplus_Ramp_Rate_{}'.format(unit.duid))  # Item3
                slack_variables.add('Surplus_Ramp_Rate_{}'.format(unit.duid))
                if hard_flag:
                    model.addConstr(unit.surplus_ramp_rate == 0, 'SURPLUS_RAMP_RATE_{}'.format(unit.duid))
                penalty += unit.surplus_ramp_rate * cvp['Unit_Ramp_Rate'] * voll
                unit.ramp_up_rate_constr = model.addConstr(unit.total_cleared - unit.surplus_ramp_rate <= unit.initial_mw + intervals * up_rate, 'ROC_UP_{}'.format(unit.duid))
                if unit.total_cleared_record is not None and unit.total_cleared_record > unit.initial_mw + intervals * up_rate and abs(unit.total_cleared_record - unit.initial_mw - intervals * up_rate) > 1:
                    logging.warning('{} {} above raise ramp rate constraint'.format(unit.dispatch_type, unit.duid))

                # Unit Ramp Rate constraint (Down)
                down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
                unit.deficit_ramp_rate = model.addVar(name='Deficit_Ramp_Rate_{}'.format(unit.duid))  # Item3
                slack_variables.add('Deficit_Ramp_Rate_{}'.format(unit.duid))
                if hard_flag:
                    model.addConstr(unit.deficit_ramp_rate == 0, 'DEFICIT_RAMP_RATE_{}'.format(unit.duid))
                penalty += unit.deficit_ramp_rate * cvp['Unit_Ramp_Rate'] * voll
                unit.ramp_down_rate_constr = model.addConstr(unit.total_cleared + unit.deficit_ramp_rate >= unit.initial_mw - intervals * down_rate, 'ROC_DOWN_{}'.format(unit.duid))
                if unit.total_cleared_record is not None and unit.total_cleared_record < unit.initial_mw - intervals * down_rate and abs(unit.total_cleared_record - unit.initial_mw + intervals * down_rate) > 1:
                    logging.warning('{} {} below down ramp rate constraint'.format(unit.dispatch_type, unit.duid))
                    logging.debug(f'{unit.dispatch_type} {unit.duid} energy target {unit.total_cleared_record} initial {unit.initial_mw} rate {down_rate}')

                # Marginal loss factor
                if unit.transmission_loss_factor is None:
                    logging.error('{} {} has no MLF.'.format(unit.dispatch_type, unit.duid))
                    unit.transmission_loss_factor = 1.0
                # Cost of an unit
                unit.cost = sum([o * (p / unit.transmission_loss_factor) for o, p in zip(unit.offers, unit.energy.price_band)])
                if unit.dispatch_type == 'GENERATOR':
                    # Add cost to objective
                    cost += unit.cost
                    # Add generation to region generation
                    regions[unit.region_id].dispatchable_generation += unit.total_cleared
                    regions[unit.region_id].dispatchable_generation_temp += unit.total_cleared_record
                    if unit.forecast_poe50 is None:
                        regions[unit.region_id].available_generation += unit.energy.max_avail
                elif unit.dispatch_type == 'LOAD':
                    # Minus cost from objective
                    cost -= unit.cost
                    # Add load to region load
                    regions[unit.region_id].dispatchable_load += unit.total_cleared
                    regions[unit.region_id].dispatchable_load_temp += unit.total_cleared_record
                    regions[unit.region_id].available_load += unit.energy.max_avail
                else:
                    logging.error('{} has no dispatch type.'.format(unit.duid))

                # Fixed loading
                if unit.energy.fixed_load != 0:
                    unit.deficit_fixed_loading = model.addVar(name='Deficit_Fixed_Loading_{}'.format(unit.duid))  # Item13
                    slack_variables.add('Deficit_Fixed_Loading_{}'.format(unit.duid))
                    if hard_flag:
                        model.addConstr(unit.deficit_fixed_loading == 0, 'DEFICIT_FIXED_LOADING_{}'.format(unit.duid))
                    unit.surplus_fixed_loading = model.addVar(name='Surplus_Fixed_Loading_{}'.format(unit.duid))  # Item13
                    slack_variables.add('Deficit_Fixed_Loading_{}'.format(unit.duid))
                    if hard_flag:
                        model.addConstr(unit.surplus_fixed_loading == 0, 'SURPLUS_FIXED_LOADING_{}'.format(unit.duid))
                    penalty += (unit.deficit_fixed_loading + unit.surplus_fixed_loading) * cvp['Energy_Inflexible_Offer'] * voll
                    model.addConstr(unit.total_cleared - unit.surplus_fixed_loading + unit.deficit_fixed_loading == unit.energy.fixed_load, 'FIXED_LOAD_{}'.format(unit.duid))
                    if unit.total_cleared_record is not None and unit.total_cleared_record != unit.energy.fixed_load:
                        logging.warning('{} {} total cleared record {} not equal to fixed load {}'.format(unit.dispatch_type, unit.duid, unit.total_cleared_record, unit.energy.fixed_load))

            # Unit is registered for FCAS only
            else:
                unit.total_cleared = 0.0
            
            # Unit participates in FCAS markets
            if unit.energy is not None and unit.fcas_bids != {} and fcas_flag:
                for bid_type, fcas in unit.fcas_bids.items():
                    # Scale for AGC (for regulating services only)
                    if bid_type == 'RAISEREG':
                        # Scale for AGC enablement limits (for dispatch and 1st interval of predispatch and 5min)
                        if condition1(process, i):
                            if fcas.enablement_max > unit.raisereg_enablement_max:
                                # print(f'1: {unit.duid}')
                                fcas.high_breakpoint = fcas.high_breakpoint + unit.raisereg_enablement_max - fcas.enablement_max
                                fcas.enablement_max = unit.raisereg_enablement_max
                            if fcas.enablement_min < unit.raisereg_enablement_min:
                                # print(f'2: {unit.duid}')
                                fcas.low_breakpoint = fcas.low_breakpoint + unit.raisereg_enablement_min - fcas.enablement_min
                                fcas.enablement_min = unit.raisereg_enablement_min
                        # Scale for AGC ramp rates (for dispatch and 1st interval of 5min predispatch)
                        if condition2(process, i) and fcas.max_avail > unit.raisereg_availability:
                            # print(f'3: {unit.duid}')
                            fcas.low_breakpoint = fcas.low_breakpoint - (fcas.max_avail - unit.raisereg_availability) * (fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
                            fcas.high_breakpoint = fcas.high_breakpoint + (fcas.max_avail - unit.raisereg_availability) * (fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
                            fcas.max_avail = unit.raisereg_availability
                    elif bid_type == 'LOWERREG':
                        # Scale for AGC enablement limits
                        if condition1(process, i):
                            if fcas.enablement_max > unit.lowerreg_enablement_max:
                                # print(f'4: {unit.duid}')
                                fcas.high_breakpoint = fcas.high_breakpoint + unit.lowerreg_enablement_max - fcas.enablement_max
                                fcas.enablement_max = unit.lowerreg_enablement_max
                            if fcas.enablement_min < unit.lowerreg_enablement_min:
                                # print(f'5: {unit.duid}')
                                fcas.low_breakpoint = fcas.low_breakpoint + unit.lowerreg_enablement_min - fcas.enablement_min
                                fcas.enablement_min = unit.lowerreg_enablement_min
                        # Scale for AGC ramp rates
                        if condition2(process, i) and fcas.max_avail > unit.lowerreg_availability:
                            # print(f'6: {unit.duid}')
                            fcas.low_breakpoint = fcas.low_breakpoint - (fcas.max_avail - unit.lowerreg_availability) * (fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
                            fcas.high_breakpoint = fcas.high_breakpoint + (fcas.max_avail - unit.lowerreg_availability) * (fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
                            fcas.max_avail = unit.lowerreg_availability
                    # Scale for UIGF (for both regulating and contingency services)
                    if unit.forecast_poe50 is not None:
                        # print(f'7: {unit.duid}')
                        fcas.high_breakpoint = fcas.high_breakpoint - (fcas.enablement_max - min(fcas.enablement_max, unit.forecast_poe50))
                        fcas.enablement_max = min(fcas.enablement_max, unit.forecast_poe50)
                    # if unit.duid == 'BW01' and bid_type == 'LOWERREG':
                    #     print(f'enable min: {fcas.enablement_min}')
                    #     print(f'low break: {fcas.low_breakpoint}')
                    #     print(f'enable max: {fcas.enablement_max}')
                    #     print(f'high break: {fcas.high_breakpoint}')
                    #     print(f'avail: {fcas.max_avail}')
                    # Check pre-conditions for enabling FCAS
                    if enable_fcas(fcas, unit, process, i):
                        fcas.value = model.addVar(ub=fcas.max_avail, name='{}_Target_{}'.format(fcas.bid_type, unit.duid))
                        fcas.lower_slope_coeff = (fcas.low_breakpoint - fcas.enablement_min) / fcas.max_avail
                        fcas.upper_slope_coeff = (fcas.enablement_max - fcas.high_breakpoint) / fcas.max_avail
                    # Verify flag
                    if unit.flags[bid_type] % 2 != fcas.flag % 2:
                        logging.warning('{} {} {} record {} but {}'.format(unit.dispatch_type, unit.duid, bid_type, unit.flags[bid_type], fcas.flag))
                    # if unit.flags[bid_type] == 3:
                    #     if fcas.flag != 1:
                    #         logging.warning('{} {} {} record 3 (trapped) but {}'.format(unit.dispatch_type, unit.duid, bid_type, fcas.flag))
                    # elif unit.flags[bid_type] != fcas.flag:
                    #     logging.warning('{} {} {} record {} but {}'.format(unit.dispatch_type, unit.duid, bid_type, unit.flags[bid_type], fcas.flag))

                for bid_type, fcas in unit.fcas_bids.items():
                    if fcas.enablement_status == 1:
                        fcas.offers = [model.addVar(ub=avail, name='{}_Avail_{}'.format(bid_type, unit.duid)) for avail in fcas.band_avail]
                        model.addConstr(fcas.value == sum(fcas.offers), '{}_{}'.format(bid_type, unit.duid))
                        fcas.cost = sum([g * p for g, p in zip(fcas.offers, fcas.price_band)])
                        # Add cost to objective
                        cost += fcas.cost
                        if bid_type == 'RAISEREG' or bid_type == 'LOWERREG':
                            # Joint ramping constraint
                            if condition2(process, i):
                                if unit.energy is not None and bid_type == 'RAISEREG':
                                    up_rate = unit.energy.roc_up if unit.ramp_up_rate is None else unit.ramp_up_rate / 60
                                    if up_rate > 0:
                                        unit.r5re_joint_ramp_surplus = model.addVar(name='R5RE_Joint_Ramp_Surplus_{}'.format(unit.duid))  # Item19
                                        slack_variables.add('R5RE_Joint_Ramp_Surplus_{}'.format(unit.duid))
                                        if hard_flag:
                                            model.addConstr(unit.r5re_joint_ramp_surplus == 0, 'R5RE_JOINT_RAMP_SURPLUS_{}'.format(unit.duid))
                                        penalty += unit.r5re_joint_ramp_surplus * cvp['FCAS_Joint_Ramping'] * voll
                                        model.addConstr(unit.total_cleared + fcas.value - unit.r5re_joint_ramp_surplus <= unit.initial_mw + intervals * up_rate)
                                        if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + unit.target_record[bid_type] > unit.initial_mw + intervals * up_rate:
                                            if abs(unit.total_cleared_record + unit.target_record[bid_type] - unit.initial_mw - intervals * up_rate) > 1:
                                                logging.warning('{} {} above raise joint ramping constraint'.format(unit.dispatch_type, unit.duid))
                                                logging.debug('energy {} {} {} initial {} up rate {}'.format(unit.total_cleared_record, bid_type, unit.target_record[bid_type], unit.initial_mw, up_rate))

                                elif unit.energy is not None and bid_type == 'LOWERREG':
                                    down_rate = unit.energy.roc_down if unit.ramp_down_rate is None else unit.ramp_down_rate / 60
                                    if down_rate > 0:
                                        unit.l5re_joint_ramp_deficit = model.addVar(name='L5RE_Joint_Ramp_Deficit_{}'.format(unit.duid))  # Item19
                                        slack_variables.add('L5RE_Joint_Ramp_Deficit_{}'.format(unit.duid))
                                        if hard_flag:
                                            model.addConstr(unit.l5re_joint_ramp_deficit == 0, 'L5RE_JOINT_RAMP_DEFICIT_{}'.format(unit.duid))
                                        penalty += unit.l5re_joint_ramp_deficit * cvp['FCAS_Joint_Ramping'] * voll
                                        model.addConstr(unit.total_cleared - fcas.value + unit.l5re_joint_ramp_deficit >= unit.initial_mw - intervals * down_rate)
                                        if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - unit.target_record[bid_type] < unit.initial_mw - intervals * down_rate:
                                            if abs(unit.total_cleared_record - unit.target_record[bid_type] - unit.initial_mw + intervals * down_rate) > 1:
                                                logging.warning('{} {} below down joint ramping constraint'.format(unit.dispatch_type, unit.duid))
                                                logging.debug('energy {} {} {} initial {} down rate {}'.format(unit.total_cleared_record, bid_type, unit.target_record[bid_type], unit.initial_mw, down_rate))

                            # Energy and regulating FCAS capacity constraint
                            model.addConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value <= fcas.enablement_max)
                            if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] > fcas.enablement_max:
                                if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] - fcas.enablement_max) > 1:
                                    logging.warning('{} {} {} above energy and regulating FCAS capacity constraint'.format(unit.dispatch_type, unit.duid, bid_type))
                                    logging.debug('energy {} upper slop {} {} {} enablement max {}'.format(unit.total_cleared_record, fcas.upper_slope_coeff, bid_type, unit.target_record[bid_type], fcas.enablement_max))
                            model.addConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value >= fcas.enablement_min)
                            if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] < fcas.enablement_min:
                                if (unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - fcas.enablement_min) > 1:
                                    logging.warning('{} {} {} below energy and regulating FCAS capacity constraint'.format(unit.dispatch_type, unit.duid, bid_type))
                                    logging.debug('energy {} lower slop {} {} {} enablement min {}'.format(unit.total_cleared_record, fcas.lower_slope_coeff, bid_type, unit.target_record[bid_type], fcas.enablement_min))
                        else:
                            # Joint capacity constraint
                            if 'RAISEREG' in unit.fcas_bids:
                                raisereg = unit.fcas_bids['RAISEREG']
                                model.addConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value + raisereg.enablement_status * raisereg.value <= fcas.enablement_max, 'UPPER_JOINT_CAPACITY_{}_{}'.format(bid_type, unit.duid))
                                if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] + (unit.flags['RAISEREG'] % 2) * unit.target_record['RAISEREG'] > fcas.enablement_max:
                                    if abs(unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] + (unit.flags['RAISEREG'] % 2) * unit.target_record['RAISEREG'] - fcas.enablement_max) > 0.01:
                                        logging.warning('{} {} {} above joint capacity constraint'.format(unit.dispatch_type, unit.duid, bid_type))
                            else:
                                model.addConstr(unit.total_cleared + fcas.upper_slope_coeff * fcas.value <= fcas.enablement_max, 'UPPER_JOINT_CAPACITY_{}_{}'.format(bid_type, unit.duid))
                                if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record + fcas.upper_slope_coeff * unit.target_record[bid_type] > fcas.enablement_max:
                                    logging.warning('{} {} {} without raisereg above joint capacity constraint'.format(unit.dispatch_type, unit.duid, bid_type))
                            if 'LOWERREG' in unit.fcas_bids:
                                lowerreg = unit.fcas_bids['LOWERREG']
                                model.addConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value - lowerreg.enablement_status * lowerreg.value >= fcas.enablement_min, 'LOWER_JOINT_CAPACITY_{}_{}'.format(bid_type, unit.duid))
                                if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - (unit.flags['LOWERREG'] % 2) * unit.target_record['LOWERREG'] < fcas.enablement_min:
                                    if abs(unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] - (unit.flags['LOWERREG'] % 2) * unit.target_record['LOWERREG'] - fcas.enablement_min) > 0.01:
                                        logging.warning('{} {} {} below joint capacity constraint'.format(unit.dispatch_type, unit.duid, bid_type))
                                        logging.debug('energy {} lower slope {} target {} status {} lowerreg {} enablemin {}'.format(unit.total_cleared_record, fcas.lower_slope_coeff, unit.target_record[bid_type], unit.flags['LOWERREG'] % 2, unit.target_record['LOWERREG'], fcas.enablement_min))
                            else:
                                model.addConstr(unit.total_cleared - fcas.lower_slope_coeff * fcas.value >= fcas.enablement_min, 'LOWER_JOINT_CAPACITY_{}_{}'.format(bid_type, unit.duid))
                                if unit.total_cleared_record is not None and unit.target_record and unit.total_cleared_record - fcas.lower_slope_coeff * unit.target_record[bid_type] < fcas.enablement_min:
                                    logging.warning('{} {} {} without lowerreg below joint capacity constraint'.format(unit.dispatch_type, unit.duid, bid_type))

                    # Add to region FCAS local dispatch
                    if unit.region_id is None:
                        logging.error('{} has no region'.format(unit.duid))
                    else:
                        regions[unit.region_id].fcas_local_dispatch_temp[bid_type] += fcas.value
                        regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += unit.target_record[bid_type]
            elif unit.energy is None and unit.fcas_bids != {} and fcas_flag:
                for bid_type, fcas in unit.fcas_bids.items():
                    fcas.offers = [model.addVar(ub=avail, name='{}_Avail{}_{}'.format(bid_type, no, unit.duid)) for no, avail in enumerate(fcas.band_avail)]
                    model.addConstr(fcas.value == sum(fcas.offers), '{}_{}'.format(bid_type, unit.duid))
                    fcas.cost = sum([o * p for o, p in zip(fcas.offers, fcas.price_band)])
                    # Add cost to objective
                    cost += fcas.cost
                    # FCAS MaxAvail constraint
                    fcas.max_avail_deficit = model.addVar(name='FCAS_Max_Avail_Deficit_{}_{}'.format(bid_type, unit.duid))  # Item18
                    slack_variables.add('FCAS_Max_Avail_Deficit_{}_{}'.format(bid_type, unit.duid))
                    if hard_flag:
                        model.addConstr(fcas.max_avail_deficit == 0, 'FCAS_MAX_AVAIL_DEFICIT_{}_{}'.format(bid_type, unit.duid))
                    penalty += fcas.max_avail_deficit * cvp['FCAS_MaxAvail'] * voll
                    fcas.max_avail_constr = model.addConstr(fcas.value - fcas.max_avail_deficit <= fcas.max_avail, 'FCAS_MAX_AVAIL_{}_{}'.format(bid_type, unit.duid))
                    if unit.target_record and unit.target_record[bid_type] > fcas.max_avail:
                        logging.warning('{} {} {} {} above max avail {} constraint'.format(unit.dispatch_type, unit.duid, bid_type, unit.target_record[bid_type], fcas.max_avail))
                    # Add to region FCAS local dispatch
                    if unit.region_id is None:
                        logging.error('{} has no region'.format(unit.duid))
                    else:
                        regions[unit.region_id].fcas_local_dispatch_temp[bid_type] += fcas.value
                        regions[unit.region_id].fcas_local_dispatch_record_temp[bid_type] += unit.target_record[bid_type]

        for region_id, region in regions.items():
            for bid_type, target in region.fcas_local_dispatch_temp.items():
                region.fcas_local_dispatch[bid_type] = model.addVar(name='Local_Dispatch_{}_{}'.format(bid_type, region_id))
                model.addConstr(region.fcas_local_dispatch[bid_type] == target, 'LOCAL_DISPATCH_{}_{}'.format(bid_type, region_id))

        generic_slack_variables = set()
        if constr_flag:
            constraints = constrain.get_constraints(process, current, units, connection_points, interconnectors, regions, start, fcas_flag)
            for constr in constraints.values():
                if condition3(process, constr.dispatch, constr.predispatch, constr.rhs) and constr.connection_point_flag:
                    if constr.constraint_type == '<=':
                        constr.surplus = model.addVar(name='Surplus_{}'.format(constr.gen_con_id))
                        generic_slack_variables.add('Surplus_{}'.format(constr.gen_con_id))
                        penalty += constr.surplus * constr.generic_constraint_weight * voll
                        constr.constr = model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus <= constr.rhs, constr.gen_con_id)
                        if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record > constr.rhs:
                            logging.warning('{} Constraint {} is violated'.format(constr.constraint_type, constr.gen_con_id))
                    elif constr.constraint_type == '=':
                        constr.deficit = model.addVar(name='Deficit_{}'.format(constr.gen_con_id))
                        generic_slack_variables.add('Deficit_{}'.format(constr.gen_con_id))
                        constr.surplus = model.addVar(name='Surplus_{}'.format(constr.gen_con_id))
                        generic_slack_variables.add('Surplus_{}'.format(constr.gen_con_id))
                        penalty += (constr.deficit + constr.surplus) * constr.generic_constraint_weight * voll
                        constr.constr = model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs - constr.surplus + constr.deficit == constr.rhs, constr.gen_con_id)
                        if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record != constr.rhs:
                            logging.warning('{} Constraint {} is violated'.format(constr.constraint_type, constr.gen_con_id))
                    elif constr.constraint_type == '>=':
                        constr.deficit = model.addVar(name='Deficit_{}'.format(constr.gen_con_id))
                        generic_slack_variables.add('Deficit_{}'.format(constr.gen_con_id))
                        penalty += constr.deficit * constr.generic_constraint_weight * voll
                        constr.constr = model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs + constr.deficit >= constr.rhs, constr.gen_con_id)
                        if constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record < constr.rhs:
                            logging.warning('{} Constraint {} is violated'.format(constr.constraint_type, constr.gen_con_id))
                    else:
                        logging.error('Constraint {} has invalid constraint type'.format(constr.gen_con_id))
                    # Verify LHS value
                    lhs = constr.connection_point_lhs_record + constr.interconnector_lhs_record + constr.region_lhs_record
                    if abs(lhs - constr.lhs) > 0.01:
                        logging.warning('{} Constraint {} LHS record {} but {}'.format(constr.constraint_type, constr.gen_con_id, constr.lhs, lhs))
                        if len(constr.connection_points) > 1 or len(constr.interconnectors) > 1 or len(constr.regions) > 1:
                            logging.debug(constr.connection_points)
                            logging.debug(constr.interconnectors)
                            logging.debug(constr.regions)

                    # # Force lhs equal lhs record
                    # model.addConstr(constr.connection_point_lhs + constr.interconnector_lhs + constr.region_lhs == constr.lhs, constr.gen_con_id)

        # Verify region record
        for region_id, region in regions.items():
            if abs(region.dispatchable_generation_record - region.dispatchable_generation_temp) > 0.01:
                logging.warning('Region {} dispatchable generation record {} but sum of total cleared {}'.format(region_id, region.dispatchable_generation_record, region.dispatchable_generation_temp))
            if abs(region.dispatchable_load_record - region.dispatchable_load_temp) > 0.01:
                logging.warning('Region {} dispatchable load record {} but sum of total cleared {}'.format(region_id, region.dispatchable_load_record, region.dispatchable_load_temp))
            if abs(region.available_generation_record - region.available_generation) > 0.01:
                logging.warning('Region {} available generation record {} but our calculation {}'.format(region_id, region.available_generation_record, region.available_generation))
            if abs(region.available_load_record - region.available_load) > 0.01:
                logging.warning('Region {} available load record {} but our calculation {}'.format(region_id, region.available_load_record, region.available_load))
            for bid_type, record in region.fcas_local_dispatch_record.items():
                if abs(record - region.fcas_local_dispatch_record_temp[bid_type]) > 0.01:
                    logging.warning('Region {} {} record {} but sum of target {}'.format(region_id, bid_type, record, region.fcas_local_dispatch_record_temp[bid_type]))

        # Set objective
        model.setObjective(cost + penalty, gurobipy.GRB.MINIMIZE)

        # Calculate marginal prices
        prices = {}
        if dual_flag:
            # Optimize model
            model.optimize()

            if model.status == gurobipy.GRB.Status.UNBOUNDED:
                logging.error('The model cannot be solved because it is unbounded')
                return None
            elif model.status == gurobipy.GRB.Status.INFEASIBLE:
                logging.debug('The model is infeasible; computing IIS')
                model.computeIIS()
                logging.debug('\nThe following constraint(s) cannot be satisfied:')
                for c in model.getConstrs():
                    if c.IISConstr:
                        logging.debug('Constraint name: {}'.format(c.constrName))
                        logging.debug('Constraint sense: {}'.format(c.sense))
                        logging.debug('Constraint rhs: {}'.format(c.rhs))
                return None
            elif model.status == gurobipy.GRB.Status.OPTIMAL:
                # Get dual total_cleared of regional energy balance constraint
                for region in regions.values():
                    prices[region.region_id] = region.rrp_constr.pi

                # # Check slack variables for soft constraints
                # if not hard_flag:
                #     for region_id, region in regions.items():
                #         logging.debug('{} Deficit: {}'.format(region_id, region.deficit_gen.x))
                #         logging.debug('{} Surplus: {}'.format(region_id, region.surplus_gen.x))
                #     logging.debug('Slack variables:')
                #     for name in slack_variables:
                #         var = model.getVarByName(name)
                #         if var.x != 0:
                #             logging.debug('{}'.format(var))
                #     logging.debug('Slack variables for generic constraints:')
                #     for name in generic_slack_variables:
                #         var = model.getVarByName(name)
                #         if var.x != 0:
                #             logging.debug('{}'.format(var))

        else:
            for region_name in [None, 'NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1']:
                for region_id, region in regions.items():
                    if region_name is None:
                        region.deficit_gen = model.addVar(name='Deficit_Gen_{}'.format(region_id))  # Item20
                        slack_variables.add('Deficit_Gen_{}'.format(region_id))
                        if hard_flag:
                            model.addConstr(region.deficit_gen == 0, 'DEFICIT_GEN_{}'.format(region_id))
                        penalty += region.deficit_gen * cvp['Region_Load_Shedding'] * voll
                        region.surplus_gen = model.addVar(name='Surplus_Gen_{}'.format(region_id))  # Item21
                        slack_variables.add('Deficit_Gen_{}'.format(region_id))
                        if hard_flag:
                            model.addConstr(region.surplus_gen == 0, 'SURPLUS_GEN_{}'.format(region_id))
                        penalty += region.surplus_gen * cvp['Excess_Generation'] * voll
                        region.rrp_constr = model.addConstr(
                            region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + region.dispatchable_load + region.losses,
                            'REGION_BALANCE_{}'.format(region_id))
                        if abs(
                                region.dispatchable_generation_record + region.net_mw_flow_record - region.total_demand - region.dispatchable_load_record - region.losses_record) > 0.01:
                            logging.warning('Region {} imbalance lhs = {} rhs = {}'.format(region_id,
                                                                                           region.dispatchable_generation_record + region.net_mw_flow_record,
                                                                                           region.total_demand + region.dispatchable_load_record + region.losses_record))
                    else:
                        model.remove(region.rrp_constr)
                        increase = 1 if region_id == region_name else 0
                        region.rrp_constr = model.addConstr(
                            region.dispatchable_generation + region.net_mw_flow + region.deficit_gen - region.surplus_gen == region.total_demand + increase + region.dispatchable_load + region.losses,
                            'REGION_BALANCE_{}'.format(region_id))
                model.optimize()

                if model.status == gurobipy.GRB.Status.INFEASIBLE:
                    logging.debug('The model is infeasible; computing IIS')
                    model.computeIIS()
                    logging.debug('\nThe following constraint(s) cannot be satisfied:')
                    for c in model.getConstrs():
                        if c.IISConstr:
                            logging.debug('Constraint name: {}'.format(c.constrName))
                            logging.debug('Constraint sense: {}'.format(c.sense))
                            logging.debug('Constraint rhs: {}'.format(c.rhs))
                    return None

                if region_name is None:
                    base = cost.getValue()
                    # Get dual total_cleared of regional energy balance constraint
                    # for region in regions.values():
                    #     region.rrp = 0 if link_flag else region.rrp_constr.pi
                    # Generate result csv
                    result.generate_dispatchload(units, current, start, process)
                    result.generate_result_csv(process, start, current, model.objVal, solution.total_objective,
                                               interconnectors, regions, units, fcas_flag)
                else:
                    prices[region_name] = cost.getValue() - base
        result.add_prices(process, start, current, prices)
        if process == 'dispatch':
            result.generate_dispatchis(start, current, regions, prices)
        elif process == 'predispatch':
            result.generate_predispatchis(start, current, interval, regions, prices)
        else:
            result.generate_p5min(start, current, regions, prices)
        return prices

    # except gurobipy.GurobiError as e:
    #     print('Error code ' + str(e.errno) + ": " + str(e))
    except AttributeError as e:
        print('Encountered an attribute error: ' + str(e))


def read_cvp():
    input_dir = preprocess.DATA_DIR / 'CVP.json'
    with input_dir.open() as f:
        return json.load(f)


def get_intervals(process):
    dispatch_intervals = 288
    p5min_intervals = 12
    if process == 'dispatch':
        return dispatch_intervals
    elif process == 'p5min':
        return p5min_intervals
    else:
        pre_dir = preprocess.DATA_DIR / 'predispatch_intervals.json'
        with pre_dir.open() as f:
            return json.load(f)[start_time.strftime('%H:%M')]


if __name__ == '__main__':
    cvp = read_cvp()
    start_time = datetime.datetime(2020, 6, 1, 4, 5, 0)
    process_type = 'dispatch'
    # process_type = 'p5min'
    path_to_log = preprocess.LOG_DIR / '{}_{}.log'.format(process_type, preprocess.get_case_datetime(start_time))
    logging.basicConfig(filename=path_to_log, filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.DEBUG)
    intervals = get_intervals(process_type)
    flag = True
    region_names = {'NSW1', 'TAS1', 'VIC1', 'SA1', 'QLD1'}
    for interval in range(1):
        # flag, cost = dispatch(cvp, start_time, interval, process_type, hard_flag=True, fcas_flag=True, constr_flag=True, losses_flag=True)
        # if not flag:
        #     flag, cost = dispatch(cvp, start_time, interval, process_type, hard_flag=False, fcas_flag=True, constr_flag=True, losses_flag=True)
        # if not flag:
        #     break
        prices = dispatch(cvp, start_time, interval, process_type)
        # print(prices)
