import logging


def verify_region_record(regions):
    # Verify region record
    for region_id, region in regions.items():
        # print(f'{region_id} net interchange record {region.net_interchange_record} calculate {region.net_interchange_record_temp}')
        if abs(region.dispatchable_generation_record - region.dispatchable_generation_temp) > 1:
            logging.warning(
                f'Region {region_id} dispatchable generation record {region.dispatchable_generation_record} but sum of total cleared {region.dispatchable_generation_temp}')
        if abs(region.dispatchable_load_record - region.dispatchable_load_temp) > 1:
            logging.warning(
                f'Region {region_id} dispatchable load record {region.dispatchable_load_record} but sum of total cleared {region.dispatchable_load_temp}')
        if abs(region.available_generation_record - region.available_generation) > 1:
            logging.warning(
                f'Region {region_id} available generation record {region.available_generation_record} but our calculation {region.available_generation}')
        if abs(region.available_load_record - region.available_load) > 1:
            logging.warning(
                f'Region {region_id} available load record {region.available_load_record} but our calculation {region.available_load}')
        for bid_type, record in region.fcas_local_dispatch_record.items():
            # print(f'{region_id} {bid_type} record {record} sum {region.fcas_local_dispatch_record_temp[bid_type]}')
            if abs(record - region.fcas_local_dispatch_record_temp[bid_type]) > 1:
                logging.warning(
                    f'Region {region_id} {bid_type} record {record} but sum of target {region.fcas_local_dispatch_record_temp[bid_type]}')


def verify_binding_constr(model, constraints):
    for constr in model.getConstrs():
        if constr.slack is not None and constr.slack != 0 and constr.constrName in constraints and constraints[
            constr.constrName].bind_flag:
            logging.warning(f'Constraint {constr.constrName} is not binding but record is')
        # elif constr.slack is not None and constr.slack == 0 and not constr.bind_flag:
        #     logging.info(f'Constraint {constr.constrName} is binding but record not.')


def debug_infeasible_model(model):
    print('Infeasible model!!!')
    logging.debug('The model is infeasible; computing IIS')
    model.computeIIS()
    logging.debug('\nThe following constraint(s) cannot be satisfied:')
    for c in model.getConstrs():
        if c.IISConstr:
            logging.debug(f'Constraint name: {c.constrName}')
            logging.debug(f'Constraint sense: {c.sense}')
            logging.debug(f'Constraint rhs: {c.rhs}')


def calculate_marginal_prices_by_definition(units, regions, prices):
    # Calculate marginal price
    for unit in units.values():
        if unit.energy is not None and unit.total_cleared.x > 0:
            for target, price in zip(unit.offers, unit.energy.price_band):
                if target.x > 0 and (prices[unit.region_id] is None or prices[
                    unit.region_id] < price / unit.transmission_loss_factor):
                    prices[unit.region_id] = price / unit.transmission_loss_factor
                    regions[unit.region_id].debug_duid = unit.duid

    # Verify marginal price for debugging
    # for region in regions.values():
    #     region.rrp = prices[region.region_id]
    #     unit = units[region.debug_duid]
    #     print(f'{region.region_id} {unit.dispatch_type} {region.debug_duid}')
    #     print(f'target {unit.total_cleared.x} record {unit.total_cleared_record} MLF {unit.transmission_loss_factor}')
    #     for t, p, a in zip(unit.offers, unit.energy.price_band, unit.energy.band_avail):
    #         print(f'Dispatch Target {t.x} Avail {a} at Price {p / unit.transmission_loss_factor}')
    # Sort by band price
    class Band:
        def __init__(self, target, avail, price, duid, mlf, bid_type, dispatch_type):
            self.target = target
            self.avail = avail
            self.price = price
            self.duid = duid
            self.mlf = mlf
            self.rrp = price / mlf
            self.bid_type = bid_type
            self.dispatch_type = dispatch_type

    def getKey(band):
        return band.rrp if band.bid_type == 'ENERGY' else band.price

    generators = {'NSW1': [], 'VIC1': [], 'TAS1': [], 'SA1': [], 'QLD1': []}
    loads = {'NSW1': [], 'VIC1': [], 'TAS1': [], 'SA1': [], 'QLD1': []}
    for duid, unit in units.items():
        if unit.energy is not None and unit.total_cleared.x > 0:
            dic = generators if unit.dispatch_type == 'GENERATOR' else loads
            for target, price, avail in zip(unit.offers, unit.energy.price_band, unit.energy.band_avail):
                if target.x > 0:
                    dic[unit.region_id].append(
                        Band(target, avail, price, duid, unit.transmission_loss_factor, 'ENERGY', unit.dispatch_type))
        if unit.fcas_bids != {}:
            for bid_type, fcas in unit.fcas_bids.items():
                if fcas.x > 0:
                    for target, price, avail in zip(fcas.offers, fcas.price_band, fcas.band_avail):
                        if target.x > 0:
                            generators[unit.region_id].append(
                                Band(target, avail, price, duid, unit.transmission_loss_factor, bid_type,
                                     unit.dispatch_type))
    import csv
    import preprocess
    # for dic, type, reverse_flag in zip([generators, loads], ['GENERATORS', 'LOADS'], [True, False]):
    #     for region_id, list in dic.items():
    #         list.sort(key=getKey, reverse=reverse_flag)
    #         dir = preprocess.OUT_DIR / f'{type}_{region_id}.csv'
    #         with dir.open(mode='w') as result_file:
    #             writer = csv.writer(result_file, delimiter=',')
    #             writer.writerow(['DUID', 'Var Name', 'Dispatch Target', 'Avail', 'RRP', 'Price', 'Loss Factor'])
    #             for band in list:
    #                 writer.writerow([band.duid, band.target.VarName, band.target.x, band.avail, band.rrp, band.price, band.mlf])

    for region_id in generators.keys():
        dir = preprocess.OUT_DIR / f'{region_id}.csv'
        with dir.open(mode='w') as result_file:
            writer = csv.writer(result_file, delimiter=',')
            for dic, dispatch_type, reverse_flag in zip([generators, loads], ['GENERATOR', 'LOAD'], [True, False]):
                row1 = ['Region ID', 'AEMO Regional Reference Price',
                        'Total Generation' if dispatch_type == 'GENERATOR' else 'Total Load']
                row2 = [region_id, regions[region_id].rrp_record,
                        regions[region_id].dispatchable_generation_record if dispatch_type == 'GENERATOR' else regions[
                            region_id].dispatchable_load_record]
                for bid_type, record in regions[region_id].fcas_local_dispatch_record.items():
                    row1.append(bid_type)
                    row2.append(record)
                l = dic[region_id]
                l.sort(key=getKey, reverse=reverse_flag)
                writer.writerow(['Bid Type', 'Dispatch Type', 'Unit ID', 'Var Name', 'Dispatch Target', 'Availability',
                                 'Price/Loss Factor', 'Price', 'Loss Factor'])
                for band in l:
                    writer.writerow(
                        [band.bid_type, band.dispatch_type, band.duid, band.target.VarName, band.target.x, band.avail,
                         band.rrp, band.price, band.mlf])
                writer.writerow([''])
                writer.writerow([''])


def debug(model, hard_flag, regions, slack_variables, generic_slack_variables):
    # Check slack variables for soft constraints
    if not hard_flag:
        for region_id, region in regions.items():
            logging.debug('{} Deficit: {}'.format(region_id, region.deficit_gen.x))
            logging.debug('{} Surplus: {}'.format(region_id, region.surplus_gen.x))
        logging.debug('Slack variables:')
        for name in slack_variables:
            var = model.getVarByName(name)
            if var.x != 0:
                logging.debug('{}'.format(var))
        logging.debug('Slack variables for generic constraints:')
        for name in generic_slack_variables:
            var = model.getVarByName(name)
            if var.x != 0:
                logging.debug('{}'.format(var))


def compare_total_cleared(units):
    # Compare total cleared with record
    for duid, unit in units.items():
        if unit.total_cleared_record is not None and abs(unit.total_cleared_record - (0 if type(unit.total_cleared) == float else unit.total_cleared.x)) > 1:
            print(f'{duid} {unit.total_cleared.x} record {unit.total_cleared_record}')


