import bid
from bid import Generator, Load
import datetime
import gurobipy
import interconnect
import logging
import result


five_min = datetime.timedelta(minutes=5)
one_day = datetime.timedelta(days=1)
thirty_min = datetime.timedelta(minutes=30)


def dispatch(ramp_flag=False, loss_flag=False):
    try:
        t = datetime.datetime(2019, 7, 7, 4, 5, 0)

        model = gurobipy.Model('nemde')
        obj = 0

        generators, loads, reserve_trader = bid.bid_day_offer(t)
        bid.bid_per_offer(generators, loads, t)
        # bid.add_scada_value(generators, loads, t)
        bid.add_intermittent_forecast(generators, t)
        bid.add_dispatch_record(generators, loads, t)

        regions, interconnectors, obj_record = interconnect.get_regions_and_interconnectors(t)

        for name, interconnector in interconnectors.items():
            regions[interconnector.to_region].net_mw_flow_record += interconnector.mw_flow_record
            regions[interconnector.from_region].net_mw_flow_record -= interconnector.mw_flow_record

            if loss_flag:
                interconnector.mw_flow = interconnector.mw_flow_record
                regions[interconnector.to_region].net_mw_flow += interconnector.mw_flow_record
                regions[interconnector.from_region].net_mw_flow -= interconnector.mw_flow_record
            else:
                interconnector.mw_flow = model.addVar(lb=-interconnector.reverse_cap, ub=interconnector.forward_cap,
                                                      name=name)
                regions[interconnector.to_region].net_mw_flow += interconnector.mw_flow
                regions[interconnector.from_region].net_mw_flow -= interconnector.mw_flow

        # interconnect.calculate_interconnector_losses(regions, interconnectors)
        if loss_flag:
            for region in regions.values():
                region.losses = region.dispatchable_generation_record + region.net_mw_flow_record - region.total_demand - region.dispatchable_load_record
        else:
            interconnect.calculate_interconnector_losses(model, regions, interconnectors)

        # for interconnector in interconnectors.values():
        #     regions[interconnector.from_region].losses += interconnector.mw_losses_record * interconnector.from_region_loss_share
        #     regions[interconnector.to_region].losses += interconnector.mw_losses_record * (1 - interconnector.from_region_loss_share)

        for generator in generators.values():
            # Dispatch generation for each price band
            generator.generations = [model.addVar(lb=0.0, ub=avail) for avail in generator.band_avail]
            # Total dispatch total_cleared
            generator.total_cleared = sum(generator.generations)
            # Unconstrained Intermittent Generation Forecasts (UIGF) for Dispatch
            if generator.forecast is not None:
                model.addConstr(generator.total_cleared <= generator.forecast)
            # Ramp rate flag
            if ramp_flag:
                # Raise constraint
                model.addConstr(generator.total_cleared <= generator.initial_mw + 5 * generator.roc_up)
                # Lower constraint
                model.addConstr(generator.total_cleared >= generator.initial_mw - 5 * generator.roc_down)
            if generator.mlf is None:
                logging.warning('Generator {} has no MLF.'.format(generator.duid))
                generator.mlf = 1.0
            # Cost of a generator
            generator.cost = sum([g * (p / generator.mlf) for g, p in zip(generator.generations, generator.price_band)])
            # Add cost to objective
            obj += generator.cost
            # Add generator to corresponding region
            regions[generator.region].generators.add(generator.duid)
            # Add generation to region generation
            regions[generator.region].dispatchable_generation += generator.total_cleared

        for load in loads.values():
            # Dispatch load for each price band
            load.loads = [model.addVar(lb=0.0, ub=avail) for avail in load.band_avail]
            # Total dispatch total_cleared
            load.total_cleared = sum(load.loads)
            if ramp_flag:
                # Raise constraint
                model.addConstr(load.total_cleared <= load.initial_mw + 5 * load.roc_up)
                # Lower constraint
                model.addConstr(load.total_cleared >= load.initial_mw - 5 * load.roc_down)
            if load.mlf is None:
                logging.warning('Load {} has no MLF.'.format(load.duid))
                load.mlf = 1.0
            # Cost of a load
            load.cost = sum([l * (p / load.mlf) for l, p in zip(load.loads, load.price_band)])
            # Add cost to objective
            obj -= load.cost
            # Add load to corresponding region
            regions[load.region].loads.add(load.duid)
            # Add load total_cleared to region load
            regions[load.region].dispatchable_load += load.total_cleared

        for region in regions.values():
            model.addConstr(region.dispatchable_generation + region.net_mw_flow == region.total_demand + region.dispatchable_load + region.losses, region.region_id)

        # Set objective
        model.setObjective(obj, gurobipy.GRB.MINIMIZE)
        # Optimize model
        model.optimize()

        # Get dual total_cleared of regional energy balance constraint
        for constr in model.getConstrs():
            if constr.constrName in regions:
                regions[constr.constrName].price = constr.pi

        # Generate result csv
        result.generate_result_csv(ramp_flag, loss_flag, t, model.objVal, obj_record, interconnectors, regions, generators)
        # test.test_negative_bids(generators)

    except gurobipy.GurobiError as e:
         print('Error code ' + str(e.errno) + ": " + str(e))

    # except AttributeError:
    #     print('Encountered an attribute error')


if __name__ == '__main__':
    logging.basicConfig(filename='nemde.log', filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)
    dispatch(True, False)