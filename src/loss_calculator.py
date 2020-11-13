import datetime
import interconnect
import gurobipy
import pprint
print = pprint.pprint


def calculate_losses():
    for ic in interconnectors.values():
        coefficient = ic.loss_constant - 1
        for region_id, demand in ic.demand_coefficient.items():
            coefficient += regions[region_id].total_demand * demand

        model = gurobipy.Model('LossCalculator')
        model.setParam('OutputFlag', 0)
        x_s = sorted(ic.mw_breakpoint.values())
        y_s = [0.5 * ic.loss_flow_coefficient * x * x + coefficient * x for x in x_s]
        ic.mw_flow = model.addVar(lb=-ic.import_limit, ub=ic.export_limit)
        ic.mw_losses = model.addVar(lb=-gurobipy.GRB.INFINITY)

        if ic.interconnector_id == 'T-V-MNSP1':
            for link_id, link in links.items():
                link.mw_flow = model.addVar()
            model.addSOS(gurobipy.GRB.SOS_TYPE1, [links['BLNKTAS'].mw_flow, links['BLNKVIC'].mw_flow])
            model.addConstr(links['BLNKTAS'].mw_flow - links['BLNKVIC'].mw_flow == ic.mw_flow)

        for i in range(len(x_s) - 1):
            if ic.interconnector_id == 'T-V-MNSP1':
                model.addConstr((ic.mw_losses - y_s[i]) * (x_s[i + 1] - x_s[i]) >= (y_s[i + 1] - y_s[i]) * (links['BLNKTAS'].mw_flow - x_s[i]))
                model.addConstr((ic.mw_losses - y_s[i]) * (x_s[i + 1] - x_s[i]) >= (y_s[i + 1] - y_s[i]) * (links['BLNKVIC'].mw_flow - x_s[i]))
            else:
                model.addConstr((ic.mw_losses - y_s[i]) * (x_s[i + 1] - x_s[i]) >= (y_s[i + 1] - y_s[i]) * (ic.mw_flow - x_s[i]))
        model.addConstr(ic.mw_flow == ic.mw_flow_record)

        model.setObjective(0)
        model.optimize()

        loss = ic.mw_losses.x
        if ic.interconnector_id == 'T-V-MNSP1':
            print(ic.interconnector_id)
            print('flow: {}'.format(ic.mw_flow.x))
            print('loss: {}'.format(ic.mw_losses.x))
            print('record: {}'.format(ic.mw_losses_record))
            if ic.metered_mw_flow >= 0:
                regions['TAS1'].losses += loss
            else:
                regions['VIC1'].losses += ic.mw_losses.x
            for link in links.values():
                print('{}: {}'.format(link.link_id, link.mw_flow.x))
                regions[link.from_region].losses += link.mw_flow.x * (1 - link.from_region_tlf)
                regions[link.to_region].losses += link.mw_flow.x * (1 - link.to_region_tlf)
        else:
            regions[ic.region_from].losses += loss * ic.from_region_loss_share
            regions[ic.region_to].losses += loss * (1 - ic.from_region_loss_share)
        regions[ic.region_from].net_mw_flow -= ic.mw_flow.x
        regions[ic.region_to].net_mw_flow += ic.mw_flow.x


def verify_equation():
    for region_id, region in regions.items():
        print(region_id)
        print('lhs: {}'.format(region.dispatchable_generation_record + region.net_mw_flow))
        print('rhs: {}'.format(region.total_demand + region.dispatchable_load_record + region.losses))


t = datetime.datetime(2019, 7, 20, 4, 5, 0)
for i in range(5):
    regions, interconnectors, obj_record = interconnect.get_regions_and_interconnectors(t)
    if interconnectors['T-V-MNSP1'].mw_flow_record > 0:
        links = interconnect.get_links(t)
        calculate_losses()
        verify_equation()
    t += datetime.timedelta(minutes=5)


