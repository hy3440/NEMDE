import gurobipy
import logging


def add_interconnector_capacity_constr(model, ic, ic_id, hard_flag, slack_variables, penalty, voll, cvp):
    # Interconnector Capacity Limit constraint (lower bound)
    ic.flow_deficit = model.addVar(name=f'Flow_Deficit_{ic_id}')  # Item5
    slack_variables.add(f'Flow_Deficit_{ic_id}')
    if hard_flag:
        model.addConstr(ic.flow_deficit, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'FLOW_DEFICIT_{ic_id}')
    penalty += ic.flow_deficit * cvp['Interconnector_Capacity_Limit'] * voll
    ic.import_limit_constr = model.addConstr(ic.mw_flow + ic.flow_deficit >= -ic.import_limit, name=f'IMPORT_LIMIT_{ic_id}')
    if ic.mw_flow_record is not None and ic.mw_flow_record < -ic.import_limit and abs(
            ic.mw_flow_record + ic.import_limit) > 1:
        logging.warning(f'IC {ic_id} mw flow record {ic.mw_flow_record} below import limit {-ic.import_limit}')

    # Interconnector Capacity Limit constraint (upper bound)
    ic.flow_surplus = model.addVar(name=f'Flow_Surplus_{ic_id}')  # Item5
    slack_variables.add(f'Flow_Surplus_{ic_id}')
    if hard_flag:
        model.addConstr(ic.flow_surplus, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'FLOW_SURPLUS_{ic_id}')
    penalty += ic.flow_surplus * cvp['Interconnector_Capacity_Limit'] * voll
    ic.export_limit_constr = model.addConstr(ic.mw_flow - ic.flow_surplus <= ic.export_limit, name=f'EXPORT_LIMIT_{ic_id}')
    if ic.mw_flow_record is not None and ic.mw_flow_record > ic.export_limit and abs(
            ic.mw_flow_record - ic.export_limit) > 1:
        logging.warning(f'IC {ic_id} mw flow record {ic.mw_flow_record} above export limit {ic.export_limit}')
    return penalty


def add_interconnector_limit_constr(model, ic, ic_id):
    # Interconnector Import Limit Record
    ic.import_record_constr = model.addConstr(ic.mw_flow >= ic.import_limit_record, name=f'IMPORT_LIMIT_RECORD_{ic_id}')
    if ic.mw_flow_record is not None and ic.import_limit_record is not None and ic.mw_flow_record < ic.import_limit_record and abs(
            ic.mw_flow_record - ic.import_limit_record) > 1:
        logging.warning(
            f'IC {ic_id} mw flow record {ic.mw_flow_record} below import limit record {ic.import_limit_record}')
    # Interconnector Export Limit Record
    ic.export_record_constr = model.addConstr(ic.mw_flow <= ic.export_limit_record, name=f'EXPORT_LIMIT_RECORD_{ic_id}')
    if ic.mw_flow_record is not None and ic.export_limit_record is not None and ic.mw_flow_record > ic.export_limit_record and abs(
            ic.mw_flow_record - ic.export_limit_record) > 1:
        logging.warning(f'IC {ic_id} mw flow record {ic.mw_flow_record} above export limit {ic.export_limit_record}')


def add_mnsp_ramp_constr(model, intervals, link, link_id, hard_flag, slack_variables, penalty, voll, cvp):
    # MNSPInterconnector ramp rate constraint (Up)
    if link.ramp_up_rate is not None:
        link.mnsp_up_deficit = model.addVar(name=f'MNSP_Up_Deficit_{link_id}')  # Item4
        slack_variables.add(f'MNSP_Up_Deficit_{link_id}')  # CONFUSED
        if hard_flag:
            model.addConstr(link.mnsp_up_deficit, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'MNSP_UP_DEFICIT_{link_id}')
        penalty += link.mnsp_up_deficit * cvp['MNSPInterconnector_Ramp_Rate'] * voll
        link.mnsp_up_constr = model.addConstr(
            link.mw_flow - link.mnsp_up_deficit <= link.metered_mw_flow + intervals * link.ramp_up_rate / 60,
            name=f'MNSPINTERCONNECTOR_UP_RAMP_RATE_{link_id}')
        if link.mw_flow_record is not None and link.mw_flow_record > link.metered_mw_flow + intervals * link.ramp_up_rate / 60:
            logging.warning(f'Link {link_id} above MNSPInterconnector up ramp rate constraint')
            logging.debug(
                f'MW flow {link.mw_flow_record} metered {link.metered_mw_flow} up rate {link.ramp_up_rate / 60}')

    # MNSPInterconnector ramp rate constraint (Down)
    if link.ramp_down_rate is not None:
        link.mnsp_dn_surplus = model.addVar(name=f'MNSP_Dn_Surplus_{link_id}')  # Item4
        slack_variables.add(f'MNSP_Dn_Surplus_{link_id}')  # CONFUSED
        if hard_flag:
            model.addConstr(link.mnsp_dn_surplus, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'MNSP_DN_SURPLUS_{link_id}')
        penalty += link.mnsp_dn_surplus * cvp['MNSPInterconnector_Ramp_Rate'] * voll
        link.mnsp_dn_constr = model.addConstr(
            link.mw_flow + link.mnsp_dn_surplus >= link.metered_mw_flow - intervals * link.ramp_down_rate / 60,
            name=f'MNSPINTERCONNECTOR_DN_RAMP_RATE_{link_id}')
        if link.mw_flow_record is not None and link.mw_flow_record < link.metered_mw_flow - intervals * link.ramp_down_rate / 60:
            logging.warning(f'Link {link_id} below MNSPInterconnector down ramp rate constraint')
    return penalty


def add_mnsp_total_band_constr(model, link, link_id, hard_flag, slack_variables, penalty, voll, cvp):
    # Total Band MW Offer constraint - MNSP only
    link.mnsp_offer_deficit = model.addVar(name=f'MNSP_Offer_Deficit_{link_id}')  # Item9
    slack_variables.add(f'MNSP_Offer_Deficit_{link_id}')
    if hard_flag:
        model.addConstr(link.mnsp_offer_deficit, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'MNSP_OFFER_DEFICIT_{link_id}')
    penalty += link.mnsp_offer_deficit * cvp['Total_Band_MW_Offer-MNSP'] * voll
    link.total_band_mw_offer_constr = model.addConstr(link.mw_flow + link.mnsp_offer_deficit,
                                                      sense=gurobipy.GRB.EQUAL,
                                                      rhs=sum(link.offers),
                                                      name=f'MNSP_TOTAL_BAND_MW_OFFER_{link_id}')
    return penalty


def add_mnsp_avail_constr(model, link, link_id, hard_flag, slack_variables, penalty, voll, cvp):
    # MNSP Availability constraint
    if link.max_avail is not None:
        link.mnsp_capacity_deficit = model.addVar(name=f'MNSP_Capacity_Deficit_{link_id}')  # Item15
        slack_variables.add(f'MNSP_Capacity_Deficit_{link_id}')  # CONFUSED
        if hard_flag:
            model.addConstr(link.mnsp_capacity_deficit, sense=gurobipy.GRB.EQUAL, rhs=0, name=f'MNSP_CAPACITY_DEFICIT_{link_id}')
        penalty += link.mnsp_capacity_deficit * cvp['MNSP_Availability'] * voll
        link.mnsp_availability_constr = model.addConstr(link.mw_flow - link.mnsp_capacity_deficit <= link.max_avail,
                                                        name=f'MNSP_AVAILABILITY_{link_id}')
        if link.mw_flow_record is not None and link.mw_flow_record > link.max_avail:
            logging.warning(f'Link {link_id} mw flow record {link.mw_flow_record} above max avail {link.max_avail}')
    return penalty