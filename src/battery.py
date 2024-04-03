# Basic battery model
from __future__ import division
from pulp import LpVariable, LpProblem, LpStatus, lpSum, value

# Load in data
f = open('7days_total_5mn.csv')  # household load (W)
f.readline()  # Discard header
load = [float(l) / 1000 for l in f.readlines()]  # (kW)
f = open('7days_solar_5mn.csv')  # global insolation (Wm-2)
f.readline()  # Discard header
glob = [float(l) / 1000 for l in f.readlines()]  # (kWm-2)

assert(len(load) == len(glob))

# PV parameters
###############
pv_size = 0  # nominal PV power (kW)

# Power profiles
################
pload = []  # household background load (kW)
ppv = []  # PV generation (kW)
pload = load
ppv = [1 * x * pv_size for x in glob]

# Time parameters
#################
tstep = 5 / 60  # time step duration (hours)
T = len(pload)  # number of time steps

# Tarrifs
#########
buy = 30.0  # buy price (c/kWh)
sell = 8.0  # sell price (c/kWh)
# formulation works only when sell <= buy

# Battery parameters
####################
Emax = 0  # battery capacity (kWh)
eff = 0.85  # combined battery and inverter efficiency
pmax = (2 / 7) * Emax  # battery max power (kW)
price = (3000.0 + 1000.0) / 7  # battery, installation, BOS costs estm ($/kWh)
price = price * 100 / (15 * 365 * 24)  # (c/kWh/hr)
# 15 years cycling once per day:
# http://reneweconomy.com.au/2015/tesla-says-battery-storage-already-makes-economic-sense-for-australia-consumers-40655
# We chose the continous power of 2KW for 7kWh model
# It can peak at 3.3kW but no details on for how long
# http://www.teslamotors.com/powerwall

# Battery variables
###################
E = [LpVariable(f'E_{i}', 0, None) for i in range(T)]  # battery energy (kWh)
pc = [LpVariable(f'pc_{i}', 0, None) for i in range(T)]  # battery charge (kW)
pd = [LpVariable(f'pd_{i}', 0, None) for i in range(T)]  # battery discharge (kW)

# Auxiliary variables
#####################
p = [LpVariable(f'p_{i}', None, None) for i in range(T)]  # total house power (kW)
cpow = [LpVariable(f'cpow_{i}', None, None) for i in range(T)]  # power cost (c)

# Optimisation problem
prb = LpProblem('Battery Operation')

# Objective
prb += lpSum(cpow) + price * tstep * T * Emax  # sum of costs

# Constraints
for i in range(T):
    prb += p[i] == pc[i] - pd[i] + pload[i] - ppv[i]  # total power
    prb += cpow[i] >= tstep * buy * p[i]  # power cost constraint
    prb += cpow[i] >= tstep * sell * p[i]  # power cost constraint
    prb += E[i] <= Emax  # battery capacity
    prb += pc[i] <= pmax
    prb += pd[i] <= pmax

# Battery charge state constraints
# Batteries must START and finish half charged
prb += E[0] == 0.5 * Emax + tstep * (eff * pc[0] - pd[0])  # starting energy
prb += E[T-1] == 0.5 * Emax  # finishing energy
for i in range(1, T):
    prb += E[i] == E[i-1] + tstep * (eff * pc[i] - pd[i])  # battery transitions

# Solve problem
prb.solve()

print(f'Status {LpStatus[prb.status]}')
print(f'Cost {value(prb.objective)}')
print(f'pv_size {value(pv_size)}')
print(f'Emax {value(Emax)}')

import matplotlib
import matplotlib.pyplot as plt

# Plotting results
t = [tstep * i for i in range(T)]
plt.plot(t, [value(E[i]) for i in range(T)], label='E')
plt.plot(t, [value(pc[i]) for i in range(T)], label='pc')
plt.plot(t, [value(pd[i]) for i in range(T)], label='pd')
plt.plot(t, [value(p[i]) for i in range(T)], label='p')

plt.xlabel('Time (hr)')
plt.ylabel('Power (kW) or Energy (kWh)')
plt.legend()
plt.show()
