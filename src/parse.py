import constrain
import logging
import preprocess
import xmltodict
from offer import Unit, EnergyBid, FcasBid

fcas_types = {'R5RE': 'RAISEREG',
              'L5RE': 'LOWERREG',
              'R6SE': 'RAISE6SEC',
              'L6SE': 'LOWER6SEC',
              'R60S': 'RAISE60SEC',
              'L60S': 'LOWER60SEC',
              'R5MI': 'RAISE5MIN',
              'L5MI': 'LOWER5MIN'
              }


def add_dayoffer(xml, units):
    """Add day offer.

    Args:
        xml (dict): dictionary extracted from XML
        units (dict): dictionary of units

    Returns:
        None
    """
    traders = xml['NEMSPDCaseFile']['NemSpdInputs']['TraderCollection']['Trader']
    for trader in traders:
        # if trader['@TraderID'] in units:
        #     unit = units[trader['@TraderID']]
        duid = trader['@TraderID']
        unit = Unit(duid)
        if trader['@TraderType'] == 'NORMALLY_ON_LOAD':
            unit.dispatch_type = 'LOAD'
            unit.normally_on_flag = 'Y'
        elif trader['@TraderType'] == 'LOAD':
            unit.dispatch_type = trader['@TraderType']
            unit.normally_on_flag = 'N'
        elif trader['@TraderType'] == 'GENERATOR':
            unit.dispatch_type = trader['@TraderType']
        elif trader['@TraderType'] == 'WDR':
            unit.dispatch_type = 'GENERATOR'
        else:
            print('DISPATCH TYPE ERROR')
            exit()
        unit.start_type = 'FAST' if '@FastStart' in trader else 'SLOW'
        if '@CurrentMode' in trader:
            unit.current_mode = int(trader['@CurrentMode'])
        if '@CurrentModeTime' in trader:
            unit.current_mode_time = float(trader['@CurrentModeTime'])
        for condition in trader['TraderInitialConditionCollection']['TraderInitialCondition']:
            if condition['@InitialConditionID'] == 'SCADARampUpRate':
                # scada_up_rate = float(condition['@Value'])
                # if abs(scada_up_rate - unit.ramp_up_rate) > 0.1:
                #     logging.debug(f'{unit.duid} up {unit.ramp_up_rate} roc {unit.energy.roc_up} but xml {scada_up_rate}')
                unit.ramp_up_rate = float(condition['@Value'])
            if condition['@InitialConditionID'] == 'SCADARampDnRate':
                # scada_dn_rate = float(condition['@Value'])
                # if abs(scada_dn_rate - unit.ramp_down_rate) > 0.1:
                #     logging.debug(f'{unit.duid} dn {unit.ramp_down_rate} roc {unit.energy.roc_down} but xml {scada_dn_rate}')
                unit.ramp_down_rate = float(condition['@Value'])
            if condition['@InitialConditionID'] == 'InitialMW':
                unit.initial_mw = float(condition['@Value'])
        structures = trader['TradePriceStructureCollection']['TradePriceStructure']['TradeTypePriceStructureCollection']['TradeTypePriceStructure']
        if type(structures) != list:
            structures = [structures]
        units[duid] = unit
        for structure in structures:
            if structure['@TradeType'] == 'ENOF' or structure['@TradeType'] == 'LDOF' or structure['@TradeType'] == 'DROF':
                unit.energy = EnergyBid([])
                unit.energy.price_band = [float(structure[f'@PriceBand{i}']) for i in range(1,11)]
                if '@T1' in trader:
                    unit.energy.minimum_load = int(trader['@MinLoadingMW'])
                    unit.energy.t1 = int(trader['@T1'])
                    unit.energy.t2 = int(trader['@T2'])
                    unit.energy.t3 = int(trader['@T3'])
                    unit.energy.t4 = int(trader['@T4'])
            else:
                bid_type = fcas_types[structure['@TradeType']]
                fcas_bid = FcasBid([])
                fcas_bid.bid_type = bid_type
                fcas_bid.price_band = [float(structure[f'@PriceBand{i}']) for i in range(1, 11)]
                unit.fcas_bids[bid_type] = fcas_bid


def add_peroffer(xml, units):
    """Add period offer.

    Args:
        xml (dict): dictionary extracted from XML
        units (dict): dictionary of units

    Returns:
        None
    """
    trader_periods = xml['NEMSPDCaseFile']['NemSpdInputs']['PeriodCollection']['Period']['TraderPeriodCollection'][
        'TraderPeriod']
    for trader_period in trader_periods:
        unit = units[trader_period['@TraderID']]
        unit.region_id = trader_period['@RegionID']
        if '@UIGF' in trader_period:
            unit.forecast_poe50 = float(trader_period['@UIGF'])
        trades = trader_period['TradeCollection']['Trade']
        if type(trades) != list:
            trades = [trades]
        for trade in trades:
            if trade['@TradeType'] == 'ENOF' or trade['@TradeType'] == 'LDOF' or trade['@TradeType'] == 'DROF':
                unit.ramp_up_rate = float(trade['@RampUpRate'])
                unit.ramp_down_rate = float(trade['@RampDnRate'])
                unit.energy.max_avail = float(trade['@MaxAvail'])
                unit.energy.band_avail = [float(trade[f'@BandAvail{i}']) for i in range(1, 11)]
            else:
                bid_type = fcas_types[trade['@TradeType']]
                unit.fcas_bids[bid_type].max_avail = float(trade['@MaxAvail'])
                unit.fcas_bids[bid_type].enablement_min = float(trade['@EnablementMin'])
                unit.fcas_bids[bid_type].enablement_max = float(trade['@EnablementMax'])
                unit.fcas_bids[bid_type].low_breakpoint = float(trade['@LowBreakpoint'])
                unit.fcas_bids[bid_type].high_breakpoint = float(trade['@HighBreakpoint'])
                unit.fcas_bids[bid_type].band_avail = [float(trade[f'@BandAvail{i}']) for i in range(1, 11)]


def add_case(xml):
    """Extract relevant prices from XML file.

    Args:
        xml (dict): dictionary extracted from XML

    Returns:
        (dict, int, int): violation prices, market price cap, market price fllor
    """
    case = xml['NEMSPDCaseFile']['NemSpdInputs']['Case']
    violation_prices = {}
    for name, price in case.items():
        if name == '@VoLL':
            voll = int(price)
        elif name == '@MPF':
            market_price_floor = int(price)
        elif 'Price' in name:
            violation_prices[name[1:]] = float(price)
    return violation_prices, voll, market_price_floor


def add_mnsp_peroffer(xml, links):
    """Add MNSP period offer.

    Args:
        xml (dict): dictionary extracted from XML
        links (dict): dictionary of links

    Returns:
        None
    """
    ic_periods = xml['NEMSPDCaseFile']['NemSpdInputs']['PeriodCollection']['Period']['InterconnectorPeriodCollection']['InterconnectorPeriod']
    for ic_period in ic_periods:
        if ic_period['@InterconnectorID'] == 'T-V-MNSP1':
            for mnsp_offer in ic_period['MNSPOfferCollection']['MNSPOffer']:
                link = links['BLNK' + mnsp_offer['@RegionID'][:-1]]
                link.max_avial = float(mnsp_offer['@MaxAvail'])
                link.ramp_up_rate = float(mnsp_offer['@RampUpRate'])
                link.ramp_down_rate = float(mnsp_offer['@RampDnRate'])
                link.band_avail = [float(mnsp_offer[f'@BandAvail{i}']) for i in range(1, 11)]


def add_mnsp_dayoffer(xml, links):
    """Add MNSP day offer.

    Args:
        xml (dict): dictionary extracted from XML
        links (dict): dictionary of links

    Returns:
        None
    """
    ics = xml['NEMSPDCaseFile']['NemSpdInputs']['InterconnectorCollection']['Interconnector']
    for ic in ics:
        if ic['@InterconnectorID'] == 'T-V-MNSP1':
            structures = ic['MNSPPriceStructureCollection']['MNSPPriceStructure']['MNSPRegionPriceStructureCollection']['MNSPRegionPriceStructure']
            for structure in structures:
                link = links[structure['@LinkID']]
                link.price_band = [float(structure[f'@PriceBand{i}']) for i in range(1, 11)]


def add_uigf_forecast(xml, units):
    """Add UIGF forecast.

    Args:
        xml (dict): dictionary extracted from XML
        units (dict): dictionary of units

    Returns:
        None
    """
    trader_period = xml['NEMSPDCaseFile']['NemSpdInputs']['PeriodCollection']['Period']['TraderPeriodCollection']['TraderPeriod']
    for trader in trader_period:
        if '@UIGF' in trader:
            unit = units[trader['@TraderID']]
            uigf = float(trader['@UIGF'])
            if abs(unit.forecast_poe50 - uigf) > 1:
                logging.warning(f'{unit.dispatch_type} {unit.duid} UIGF {unit.forecast_poe50} but xml {uigf}')
                unit.forecast_poe50 = uigf


def add_trader_factor(constr, lhs_factor_collection, units, fcas_flag, debug_flag=False):
    if lhs_factor_collection is not None and 'TraderFactor' in lhs_factor_collection:
        trader_factor = lhs_factor_collection['TraderFactor']

        def add_trader_constr(constr, units, item):
            trade_type = item['@TradeType']
            if trade_type == 'ENOF' or trade_type == 'LDOF' or trade_type == 'DROF':
                constr.connection_point_lhs += float(item['@Factor']) * units[item['@TraderID']].total_cleared
                if debug_flag:
                    if units[item['@TraderID']].total_cleared_record is not None:
                        constr.connection_point_lhs_record += float(item['@Factor']) * units[item['@TraderID']].total_cleared_record
            else:
                constr.fcas_flag = True
                if fcas_flag:
                    constr.connection_point_lhs += float(item['@Factor']) * (units[item['@TraderID']].fcas_bids[fcas_types[trade_type]].value if fcas_types[trade_type] in units[item['@TraderID']].fcas_bids else 0)
                    if debug_flag:
                        if units[item['@TraderID']].target_record:
                            constr.connection_point_lhs_record += float(item['@Factor']) * units[item['@TraderID']].target_record[fcas_types[trade_type]]

        if type(trader_factor) != list:
            add_trader_constr(constr, units, trader_factor)
        else:
            for item in trader_factor:
                add_trader_constr(constr, units, item)


def add_interconnector_factor(constr, lhs_factor_collection, interconnectors, debug_flag=False):
    if lhs_factor_collection is not None and 'InterconnectorFactor' in lhs_factor_collection:
        interconnector_factor = lhs_factor_collection['InterconnectorFactor']

        def add_interconnector_constr(constr, interconnectors, item):
            constr.interconnector_lhs += float(item['@Factor']) * interconnectors[item['@InterconnectorID']].mw_flow
            if debug_flag:
                constr.interconnector_lhs_record += float(item['@Factor']) * interconnectors[item['@InterconnectorID']].mw_flow_record

        if type(interconnector_factor) != list:
            add_interconnector_constr(constr, interconnectors, interconnector_factor)
        else:
            for item in interconnector_factor:
                add_interconnector_constr(constr, interconnectors, item)


def add_region_factor(constr, lhs_factor_collection, regions, fcas_flag, debug_flag=False):
    if lhs_factor_collection is not None and 'RegionFactor' in lhs_factor_collection:
        region_factor = lhs_factor_collection['RegionFactor']
        constr.fcas_flag = True

        if not fcas_flag:
            return None

        def add_region_constr(constr, regions, item):
            regions[item['@RegionID']].fcas_constraints[fcas_types[item['@TradeType']]].add(constr.gen_con_id)
            constr.region_lhs += float(item['@Factor']) * regions[item['@RegionID']].fcas_local_dispatch[fcas_types[item['@TradeType']]]
            if debug_flag:
                constr.region_lhs_record += float(item['@Factor']) * regions[item['@RegionID']].fcas_local_dispatch_record[fcas_types[item['@TradeType']]]

        if type(region_factor) != list:
            add_region_constr(constr, regions, region_factor)
        else:
            for item in region_factor:
                add_region_constr(constr, regions, item)


def add_generic_constraint(xml, units, regions, interconnectors, constraints, fcas_flag):
    types = {'LE': '<=', 'GE': '>=', 'EQ': '='}
    for generic_constr in xml['NEMSPDCaseFile']['NemSpdInputs']['GenericConstraintCollection']['GenericConstraint']:
        constr_id = generic_constr['@ConstraintID']
        if constr_id not in constraints:
            constr = constrain.Constraint(constr_id, float(generic_constr['@RHS']))
            constr.constraint_type = types[generic_constr['@Type']]
            constr.violation_price = float(generic_constr['@ViolationPrice'])
            constraints[constr_id] = constr

            lhs_factor_collection = generic_constr['LHSFactorCollection']
            add_trader_factor(constr, lhs_factor_collection, units, fcas_flag)
            add_interconnector_factor(constr, lhs_factor_collection, interconnectors)
            add_region_factor(constr, lhs_factor_collection, regions, fcas_flag)


def add_constraint_solution(xml, constraints):
    for constr_soln in xml['NEMSPDCaseFile']['NemSpdOutputs']['ConstraintSolution']:
        constr_id = constr_soln['@ConstraintID']
        if constr_id in constraints:
            constr = constraints[constr_id]
            xml_rhs = float(constr_soln['@RHS'])
            if constr.rhs is None or abs(constr.rhs - xml_rhs) > 0.1:
                constr.rhs = xml_rhs
        else:
            constr = constrain.Constraint(constr_id, float(constr_soln['@RHS']))
            constr.marginal_value = float(constr_soln['@MarginalValue'])
            constraints[constr_id] = constr


def verify_fcas(trade, fcas, duid):
    f1 = float(trade['@MaxAvail']) == fcas.max_avail
    if not f1:
        print(f'Max avail {fcas.max_avail}')
        print(trade['@MaxAvail'])

    f2 = float(trade['@EnablementMin']) == fcas.enablement_min
    if not f2:
        print(f'Enablement Min {fcas.enablement_min}')
        print(trade['@EnablementMin'])

    f3 = float(trade['@EnablementMax']) == fcas.enablement_max
    if not f3:
        print(f'Enablement Max {fcas.enablement_max}')
        print(trade['@EnablementMax'])

    f4 = float(trade['@LowBreakpoint']) == fcas.low_breakpoint
    if not f4:
        print(f'Low Breakpoint {fcas.low_breakpoint}')
        print(trade['@LowBreakpoint'])

    f5 = float(trade['@HighBreakpoint']) == fcas.high_breakpoint
    if not f5:
        print(f'High Breakpoint {fcas.high_breakpoint}')
        print(trade['@HighBreakpoint'])

    if not (f1 and f2 and f3 and f4 and f5):
        print(f'{duid} {fcas.bid_type}')
        print(f'{f1} {f2} {f3} {f4} {f5}')


def add_fcas(trade, fcas, duid):
    fcas.max_avail = float(trade['@MaxAvail'])
    fcas.enablement_min = float(trade['@EnablementMin'])
    fcas.enablement_max = float(trade['@EnablementMax'])
    fcas.low_breakpoint = float(trade['@LowBreakpoint'])
    fcas.high_breakpoint = float(trade['@HighBreakpoint'])
    # if duid == 'HDWF2':
    #     print(fcas.bid_type)
    #     print(fcas.max_avail)
    #     print(fcas.enablement_min)
    #     print(fcas.enablement_max)
    #     print(fcas.low_breakpoint)
    #     print(fcas.high_breakpoint)


def handle_trade(trade, unit, func):
    # if unit.duid == 'HDWF2':
    #     print(f'initial {unit.initial_mw}')
    #     print(f'roc up {unit.energy.roc_up}')
    #     print(f'ramp up {unit.ramp_up_rate}')
    #     print(f'roc dn {unit.energy.roc_down}')
    #     print(f'ramp dn {unit.ramp_down_rate}')
    #     print(f'raisereg enablemax {unit.raisereg_enablement_max}')
    #     print(f'raisereg enablemin {unit.raisereg_enablement_min}')
    #     print(f'lowerreg enablemax {unit.lowerreg_enablement_max}')
    #     print(f'lowerreg enablemin {unit.lowerreg_enablement_min}')
    # if unit.duid == 'BW01' and trade['@TradeType'] == 'ENOF':  # or trade['@TradeType'] == 'LDOF':
    #     print(trade['@RampUpRate'])
    #     print(unit.energy.roc_up)
    #     print(unit.ramp_up_rate)
    #     # up_rate = float(trade['@RampUpRate'])
    #     # if unit.energy.roc_up * 60 != up_rate:
    #     #     print(f'{unit.dispatch_type} {unit.duid} up {unit.ramp_up_rate} bid {unit.energy.roc_up * 60} but {up_rate}')
    #     # dn_rate = float(trade['@RampDnRate'])
    #     # if unit.energy.roc_down * 60 != dn_rate:
    #     #     print(f'{unit.dispatch_type} {unit.duid} dn {unit.ramp_down_rate} bid {unit.energy.roc_down * 60} but {dn_rate}')
    # else:
    if True:
        for trade_type, fcas_type in fcas_types.items():
            if trade['@TradeType'] == trade_type and fcas_type in unit.fcas_bids:
                fcas = unit.fcas_bids[fcas_type]
                func(trade, fcas, unit.duid)


def add_trader_period(xml, units, func):
    trader_periods = xml['NEMSPDCaseFile']['NemSpdInputs']['PeriodCollection']['Period']['TraderPeriodCollection']['TraderPeriod']
    for trader_period in trader_periods:
        unit = units[trader_period['@TraderID']]
        if type(trader_period['TradeCollection']['Trade']) != list:
            trade = trader_period['TradeCollection']['Trade']
            handle_trade(trade, unit, func)
        else:
            for trade in trader_period['TradeCollection']['Trade']:
                handle_trade(trade, unit, func)


def read_xml(t):
    """Read XML file.

    Args:
        t (datetime.datetime): current datetime

    Returns:
        dict: XML to dict
    """
    outputs_dir = preprocess.download_xml(t)
    with outputs_dir.open() as f:
        read = f.read()
        xml = xmltodict.parse(read)
        return xml


def add_nemspdoutputs(t, units, links, link_flag, process):
    """Add required information of link from XML file.

    Args:
        t (datetime.datetime): current datetime
        units (dict): dictionary of units
        links (dict): dictionary of links
        link_flag (bool): consider link or not
        process (str): process type

    Returns:

    """
    xml = read_xml(t)
    add_dayoffer(xml, units)
    add_peroffer(xml, units)
    # if process == 'dispatch':
    #     # violation_prices = add_case(xml)
    #     add_uigf_forecast(xml, units)
    if link_flag:
        add_mnsp_peroffer(xml, links)
        add_mnsp_dayoffer(xml, links)
    # add_trader_period(xml, units, add_fcas)
    return add_case(xml)


def add_xml_constr(t, start, predispatch_t, process, units, regions, interconnectors, constraints, fcas_flag):
    xml = read_xml(t)
    add_generic_constraint(xml, units, regions, interconnectors, constraints, fcas_flag)
    add_constraint_solution(xml, constraints)
    if process == 'dispatch':
        constrain.add_dispatch_constraint(t, constraints)
    elif process == 'p5min':
        constrain.add_p5min_constraint(t, start, constraints)
    else:
        constrain.add_predispatch_constraint(predispatch_t, start, constraints)


def add_nemspdoutputs_fcas(t, units, func):
    xml = read_xml(t)
    add_trader_period(xml, units, func)


def main():
    import datetime
    t = datetime.datetime(2020, 6, 1, 4, 5)
    import offer
    units, connection_points = offer.get_units(t, t, 0, 'formulate', True)
    import interconnect
    links = interconnect.get_links(t)
    violation_prices = add_nemspdoutputs(t, units, links)


if __name__ == '__main__':
    main()
