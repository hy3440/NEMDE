import bid
from bid import Generator, Load
import datetime
import gurobipy
import interconnect
import logging
import result


def dispatch():
    try:
        delta = datetime.timedelta(minutes=5)
        t = datetime.datetime(2019, 5, 22, 4, 5, 0)
        case_date = t.strftime('%Y%m%d')  # YYmmdd
        case_datetime = t.strftime('%Y%m%d%H%M')  # YYmmddHHMM
        interval_datetime = t.strftime('%Y/%m/%d %H:%M:%S')  # YY/mm/dd HH:MM:SS

        model = gurobipy.Model('nemde')
        obj = 0

        generators, loads, reserve_trader, bids_file = bid.bid_day_offer(case_date)
        bid.bid_per_offer(generators, loads, bids_file, interval_datetime)
        bid.add_scada_value(generators, loads, case_datetime)

        regions, interconnectors, obj_record = interconnect.get_regions_and_interconnectors(case_datetime)

        for name, interconnector in interconnectors.items():
            interconnector.mwflow = model.addVar(lb=-interconnector.reverse_cap, ub=interconnector.forward_cap, name=name)
            regions[interconnector.to_region].net_interchange += interconnector.mwflow
            regions[interconnector.from_region].net_interchange -= interconnector.mwflow

        for generator in generators.values():
            # Dispatch generation for each price band
            generator.generations = [model.addVar(lb=0.0, ub=avail) for avail in generator.band_avail]
            # Total dispatch value
            generator.value = sum(generator.generations)
            # Raise constraint
            model.addConstr(generator.value <= generator.scada_value + 5 * generator.roc_up)
            # Lower constraint
            model.addConstr(generator.value >= generator.scada_value - 5 * generator.roc_down)
            # Cost of a generator
            generator.cost = sum([g * p for g, p in zip(generator.generations, generator.price_band)])
            # Add cost to objective
            obj += generator.cost
            # Add generator to corresponding region
            regions[generator.region].generators.add(generator.duid)
            # Add generation to region generation
            regions[generator.region].dispatchable_generation += generator.value

        for load in loads.values():
            # Dispatch load for each price band
            load.loads = [model.addVar(lb=0.0, ub=avail) for avail in load.band_avail]
            # Total dispatch value
            load.value = sum(load.loads)
            # Raise constraint
            model.addConstr(load.value <= load.scada_value + 5 * load.roc_up)
            # Lower constraint
            model.addConstr(load.value >= load.scada_value - 5 * load.roc_down)
            # Cost of a load
            load.cost = sum([l * p for l, p in zip(load.loads, load.price_band)])
            # Add cost to objective
            obj += load.cost
            # Add load to corresponding region
            regions[load.region].loads.add(load.duid)
            # Add load value to region load
            regions[load.region].dispatchable_load += load.value

        for region in regions.values():
            model.addConstr(region.dispatchable_generation + region.net_interchange == region.total_demand + region.dispatchable_load, region.region_id)

        # Set objective
        model.setObjective(obj, gurobipy.GRB.MINIMIZE)
        # Optimize model
        model.optimize()
        # Generate result csv
        result.generate_result_csv(interval_datetime, model.objVal, obj_record, interconnectors, regions)

    except gurobipy.GurobiError as e:
        print('Error code ' + str(e.errno) + ": " + str(e))

    except AttributeError:
        print('Encountered an attribute error')


if __name__ == '__main__':
    logging.basicConfig(filename='nemde.log', filemode='w', format='%(levelname)s: %(asctime)s %(message)s', level=logging.INFO)
    dispatch()