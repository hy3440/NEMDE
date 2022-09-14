import gurobipy


def KKT(model, quadratic=False):
    L = 1e10
    model.update()
    dual_variables = {}
    complementary_constrs = set()
    dual_obj = 0
    for var in model.getVars():
        gradient = var.Obj
        # if gradient == 0:
        #     continue
        if var.ub != gurobipy.GRB.INFINITY and var.ub != float('inf'):
            dual = model.addVar(name=f'Dual_Ub_{var.VarName}')
            # model.update()
            dual_variables[f'Dual_Ub_{var.VarName}'] = dual
            gradient += dual
            dual_obj -= dual * var.ub
            if quadratic:
                model.addQConstr(dual * (var.ub - var) == 0, name=f'COMPLEMENTARY_UB_{var.VarName}')
            else:
                binary = model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_Ub_{var.VarName}')
                model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_Ub_{var.VarName}')
                model.addConstr(var.ub - var <= binary * L, name=f'COMPLEMENTARY2_Ub_{var.VarName}')

        if var.lb != - gurobipy.GRB.INFINITY and var.lb != float('-inf'):
            dual = model.addVar(name=f'Dual_Lb_{var.VarName}')
            # model.update()
            dual_variables[f'Dual_Lb_{var.VarName}'] = dual
            gradient -= dual
            dual_obj += dual * var.lb
            if quadratic:
                model.addQConstr(dual * (var - var.lb) == 0, name=f'COMPLEMENTARY_LB_{var.VarName}')
            else:
                binary = model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_Lb_{var.VarName}')
                model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_Lb_{var.VarName}')
                model.addConstr(var - var.lb <= binary * L, name=f'COMPLEMENTARY2_Lb_{var.VarName}')

        col = model.getCol(var)
        for constr_num in range(col.size()):
            coef = col.getCoeff(constr_num)
            constr = col.getConstr(constr_num)

            dual = dual_variables.get(f'Dual_{constr.ConstrName}')
            if dual is None:
                dual = model.addVar(lb=(-gurobipy.GRB.INFINITY if constr.sense == '=' else 0), name=f'Dual_{constr.ConstrName}')
                # model.update()
                dual_variables[f'Dual_{constr.ConstrName}'] = dual
                dual_obj_part = dual * constr.rhs
            else:
                dual_obj_part = 0

            if constr.sense == '<':
                gradient += dual * coef
                dual_obj -= dual_obj_part
                constr_expr = constr.rhs
                row = model.getRow(constr)
                for var_num in range(row.size()):
                    constr_expr -= row.getVar(var_num) * row.getCoeff(var_num)
                constr_name = f'COMPLEMENTARY_{constr.ConstrName}'
                if constr_name not in complementary_constrs:
                    if quadratic:
                        model.addQConstr(dual * constr_expr == 0, name=constr_name)
                        complementary_constrs.add(constr_name)
                    else:
                        binary = model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_{constr.ConstrName}')
                        model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_{constr.ConstrName}')
                        model.addConstr(constr_expr <= binary * L, name=f'COMPLEMENTARY2_{constr.ConstrName}')
                        complementary_constrs.add(f'COMPLEMENTARY_{constr.ConstrName}')

            elif constr.sense == '>':
                gradient -= dual * coef
                dual_obj += dual_obj_part
                constr_expr = - constr.rhs
                row = model.getRow(constr)
                for var_num in range(row.size()):
                    constr_expr += row.getVar(var_num) * row.getCoeff(var_num)
                constr_name = f'COMPLEMENTARY_{constr.ConstrName}'
                if constr_name not in complementary_constrs:
                    if quadratic:
                        model.addQConstr(dual * constr_expr == 0, name=constr_name)
                        complementary_constrs.add(constr_name)
                    else:
                        binary = model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_{constr.ConstrName}')
                        model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_{constr.ConstrName}')
                        model.addConstr(constr_expr <= binary * L, name=f'COMPLEMENTARY2_{constr.ConstrName}')
                        complementary_constrs.add(f'COMPLEMENTARY_{constr.ConstrName}')

            elif constr.sense == '=':
                gradient -= dual * coef
                dual_obj += dual_obj_part

        model.addLConstr(gradient == 0, name=f'GRADIENT_{var.VarName}')
    model.update()
    return dual_variables, model, dual_obj


def copy_KKT(model, quadratic=False):
    L = 1e10
    model.update()
    kkt_model = model.copy()
    kkt_model.update()
    dual_variables = {}
    complementary_constrs = set()
    dual_obj = 0
    for original_var in model.getVars():
        var = kkt_model.getVarByName(original_var.VarName)
        gradient = var.Obj
        # if gradient == 0:
        #     continue
        if var.ub != gurobipy.GRB.INFINITY and var.ub != float('inf'):
            dual = kkt_model.addVar(name=f'Dual_Ub_{var.VarName}')
            kkt_model.update()
            dual_variables[f'Dual_Ub_{var.VarName}'] = dual
            gradient += dual
            dual_obj -= dual * var.ub
            if quadratic:
                kkt_model.addQConstr(dual * (var.ub - var) == 0, name=f'COMPLEMENTARY_UB_{var.VarName}')
            else:
                binary = kkt_model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_Ub_{var.VarName}')
                kkt_model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_Ub_{var.VarName}')
                kkt_model.addConstr(var.ub - var <= binary * L, name=f'COMPLEMENTARY2_Ub_{var.VarName}')

        if var.lb != - gurobipy.GRB.INFINITY and var.lb != float('-inf'):
            dual = kkt_model.addVar(name=f'Dual_Lb_{var.VarName}')
            kkt_model.update()
            dual_variables[f'Dual_Lb_{var.VarName}'] = dual
            gradient -= dual
            dual_obj += dual * var.lb
            if quadratic:
                kkt_model.addQConstr(dual * (var - var.lb) == 0, name=f'COMPLEMENTARY_LB_{var.VarName}')
            else:
                binary = kkt_model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_Lb_{var.VarName}')
                kkt_model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_Lb_{var.VarName}')
                kkt_model.addConstr(var - var.lb <= binary * L, name=f'COMPLEMENTARY2_Lb_{var.VarName}')

        original_col = model.getCol(original_var)
        for constr_num in range(original_col.size()):
            coef = original_col.getCoeff(constr_num)
            original_constr = original_col.getConstr(constr_num)
            constr = kkt_model.getConstrByName(original_constr.ConstrName)

            dual = dual_variables.get(f'Dual_{constr.ConstrName}')
            if dual is None:
                dual = kkt_model.addVar(lb=(-gurobipy.GRB.INFINITY if constr.sense == '=' else 0), name=f'Dual_{constr.ConstrName}')
                kkt_model.update()
                dual_variables[f'Dual_{constr.ConstrName}'] = dual
                dual_obj_part = dual * constr.rhs
            else:
                dual_obj_part = 0
            if constr.sense == '<':
                gradient += dual * coef
                dual_obj -= dual_obj_part
                constr_expr = constr.rhs
                original_row = model.getRow(original_constr)
                for var_num in range(original_row.size()):
                    constr_expr -= kkt_model.getVarByName(original_row.getVar(var_num).VarName) * original_row.getCoeff(var_num)
                constr_name = f'COMPLEMENTARY_{constr.ConstrName}'
                if constr_name not in complementary_constrs:
                    if quadratic:
                        kkt_model.addQConstr(dual * constr_expr == 0, name=constr_name)
                        complementary_constrs.add(constr_name)
                    else:
                        binary = kkt_model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_{constr.ConstrName}')
                        kkt_model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_{constr.ConstrName}')
                        kkt_model.addConstr(constr_expr <= binary * L, name=f'COMPLEMENTARY2_{constr.ConstrName}')
                        complementary_constrs.add(f'COMPLEMENTARY_{constr.ConstrName}')

            elif constr.sense == '>':
                gradient -= dual * coef
                dual_obj += dual_obj_part
                constr_expr = - constr.rhs
                original_row = model.getRow(original_constr)
                for var_num in range(original_row.size()):
                    constr_expr += kkt_model.getVarByName(original_row.getVar(var_num).VarName) * original_row.getCoeff(var_num)
                constr_name = f'COMPLEMENTARY_{constr.ConstrName}'
                if constr_name not in complementary_constrs:
                    if quadratic:
                        kkt_model.addQConstr(dual * constr_expr == 0, name=constr_name)
                        complementary_constrs.add(constr_name)
                    else:
                        binary = kkt_model.addVar(vtype=gurobipy.GRB.BINARY, name=f'Binary_{constr.ConstrName}')
                        kkt_model.addConstr(dual <= (1 - binary) * L, name=f'COMPLEMENTARY_{constr.ConstrName}')
                        kkt_model.addConstr(constr_expr <= binary * L, name=f'COMPLEMENTARY2_{constr.ConstrName}')
                        complementary_constrs.add(f'COMPLEMENTARY_{constr.ConstrName}')

            elif constr.sense == '=':
                gradient -= dual * coef
                dual_obj += dual_obj_part

        kkt_model.addLConstr(gradient == 0, name=f'GRADIENT_{var.VarName}')
    kkt_model.update()
    return dual_variables, kkt_model, dual_obj


def feasible(m, prob_id, units):
    quadratic = False
    _, model = KKT(m, quadratic)
    # _, model = copy_KKT(m, quadratic)
    model.update()
    # print(dual_variables)
    model.setObjective(0, gurobipy.GRB.MINIMIZE)
    if quadratic:
        model.params.NonConvex = 2
    model.optimize()
    print(model.getObjective())
    print(model.status)
    model.write("infeasible.lp")
    if model.status == gurobipy.GRB.Status.INFEASIBLE or model.status == gurobipy.GRB.Status.INF_OR_UNBD:
        model.computeIIS()
        print('\nThe following constraint(s) cannot be satisfied:')
        for c in model.getConstrs():
            if c.IISConstr:
                print(f'Constraint name: {c.constrName}')
                print(f'Constraint sense: {c.sense}')
                print(f'Constraint rhs: {c.rhs}')
    for region_id in ['NSW1', 'VIC1', 'QLD1', 'SA1', 'TAS1']:
        dual_value = model.getVarByName(f'Dual_REGION_BALANCE_{region_id}_{prob_id}')
        print(dual_value)
    for duid, unit in units.items():
        print(f'{duid}: {0 if type(unit.total_cleared) == float else unit.total_cleared.x}', model.getVarByName(f'Total_Cleared_{duid}_{prob_id}'))
        # print(model.getVarByName(f'Dual_TOTAL_BAND_MW_OFFER_{unit.duid}_{prob_id}'))
    exit(0)


def test_kkt():
    with gurobipy.Env() as env, gurobipy.Model(env=env, name='TestKKT') as m:
        # G0 = m.addVar(lb=0, ub=200, name='G0')
        # G1 = m.addVar(lb=0, ub=200, name='G1')
        # B0 = m.addVar(lb=0, ub=200, name='B0')
        # B1 = m.addVar(lb=0, ub=200, name='B1')

        G0 = m.addVar(lb=-gurobipy.GRB.INFINITY, name='G0')
        G1 = m.addVar(lb=-gurobipy.GRB.INFINITY, name='G1')
        B0 = m.addVar(lb=-gurobipy.GRB.INFINITY, name='B0')
        B1 = m.addVar(lb=-gurobipy.GRB.INFINITY, name='B1')
        # L0 = m.addVar(lb=-gurobipy.GRB.INFINITY, name='L0')
        # L1 = m.addVar(lb=-gurobipy.GRB.INFINITY, name='L1')
        m.update()
        # for var in [G0, G1, B0, B1, L0, L1]:
        for var in [G0, G1, B0, B1]:
            m.addLConstr(- var >= - 200, f'UpperBound_{var.VarName}')
            m.addLConstr(var >= 0, f'LowerBound_{var.VarName}')
        # G0_offers = [m.addVar(ub=20, name=f'G0_Offer{i + 1}') for i in range(10)]
        # m.addLConstr(G0 == sum(G0_offers), name='G0_SUM_OFFERS')
        D0 = 300
        D1 = 200
        # balance_constr0 = m.addLConstr(G0 + B0, gurobipy.GRB.EQUAL, D0 + L0)
        # balance_constr1 = m.addLConstr(G1 + B1, gurobipy.GRB.EQUAL, D1 + L0)
        balance_constr0 = m.addLConstr(G0 + B0, gurobipy.GRB.EQUAL, D0)
        balance_constr1 = m.addLConstr(G1 + B1, gurobipy.GRB.EQUAL, D1)
        m.addLConstr(G1 - G0 + 10 >= 0)
        # m.addSOS(gurobipy.GRB.SOS_TYPE1, [B0, L0])
        # m.addSOS(gurobipy.GRB.SOS_TYPE1, [B1, L1])
        # objective = G0 * 10 + G1 * 5 + B0 * 10 + B1 * 20 - L0 * 6 - L1 * 8
        # objective = sum(G0_offers) * 100 + G1 * 5 + B0 * 10 + B1 * 20
        objective = G0 * 100 + G1 * 5 + B0 * 10 + B1 * 20
        m.setObjective(objective, gurobipy.GRB.MINIMIZE)
        m.optimize()
        m.write("original.mps")

        # fixed = m.fixed()
        # fixed.optimize()

        # print(G0, G1, B0, B1, L0, L1)
        print(G0, G1, B0, B1)

        # for constr in m.getConstrs():
        #     print(f'{constr.ConstrName} dual is {constr.pi}')

        # dual_vars, kkt_model, dual_obj = KKT(m, quadratic=False)
        dual_vars, kkt_model, dual_obj = copy_KKT(m, quadratic=False)
        # kkt_model.params.NonConvex = 2

        # m.setObjective(0, gurobipy.GRB.MINIMIZE)
        # m.optimize()

        kkt_model.setObjective(0, gurobipy.GRB.MINIMIZE)
        kkt_model.optimize()

        if kkt_model.status == gurobipy.GRB.Status.INFEASIBLE or kkt_model.status == gurobipy.GRB.Status.INF_OR_UNBD:
            kkt_model.computeIIS()
            print('\nThe following constraint(s) cannot be satisfied:')
            for c in kkt_model.getConstrs():
                if c.IISConstr:
                    print(f'Constraint name: {c.constrName}')
                    print(f'Constraint sense: {c.sense}')
                    print(f'Constraint rhs: {c.rhs}')

        # for dual_name, dual_var in dual_vars.items():
        #     print(dual_name, dual_var.x, kkt_model.getVarByName(dual_name).x)

        for constr in m.getConstrs():
            # print(f'{constr.ConstrName} dual is {fixed.getConstrByName(constr.ConstrName).pi} KKT is', kkt_model.getVarByName(f'Dual_{constr.ConstrName}'))
            print(f'{constr.ConstrName} dual is {m.getConstrByName(constr.ConstrName).pi} KKT is', kkt_model.getVarByName(f'Dual_{constr.ConstrName}'))

        # for var_name in ['G0', 'G1', 'B0', 'B1', 'L0', 'L1']:
        for var_name in ['G0', 'G1', 'B0', 'B1']:
            print(kkt_model.getVarByName(var_name))

        print(f'primal obj is {objective.getValue()} dual obj is {dual_obj.getValue()}')

        kkt_model.write("debug.lp")


def test():
    with gurobipy.Env() as env, gurobipy.Model(env=env, name='Test') as model:
        a = model.addVar(ub=5, name='a')
        model.update()
        print('yes', a.ub)
        d = model.addVar(ub=6, name='d')
        c = model.addLConstr(3 * a == 4, 'c')
        b = model.addLConstr(5 + d >= a, 'b')
        model.update()
        model.setObjective(12 * a)
        model.update()
        print('here', d.Obj)
        print(model.getCoeff(c, a))
        print(model.getCol(a))
        col = model.getCol(a)
        for i in range(col.size()):
            coef = col.getCoeff(i)
            row = col.getConstr(i)
            print(coef)
            print(row)
            print(row.sense)
            print(type(row.sense), 'here')
        col = model.getCol(d)
        for i in range(col.size()):
            coef = col.getCoeff(i)
            row = col.getConstr(i)
            print(coef)
            print(row)
            print(row.sense)

        for cnstr in model.getConstrs():
            print("Constraint %s: sense %s, RHS=%f" % (cnstr.ConstrName, cnstr.Sense, cnstr.RHS))
            row = model.getRow(cnstr)
            for k in range(row.size()):
                print("Variable %s, coefficient %f" % (row.getVar(k).VarName, row.getCoeff(k)))


if __name__ == '__main__':
    # test()
    test_kkt()
