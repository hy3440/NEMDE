# Minimum Data Requirements

### 1. Generator Bids

 contains two parts:

1.  [`BIDDAYOFFER_D`](../assets/BIDDAYOFFER_D.pdf) (about 1047 rows) summarises generator bids per day

2. **[`BIDPEROFFER_D`](../assets/BIDPEROFFER_D.pdf)** summarises generator bids per period

**updates** daily shortly after 4am.

| Aspect  | Description                                                  |
| ------- | :----------------------------------------------------------- |
| URL     | [http://nemweb.com.au/Reports/Current/Bidmove_Summary/](http://nemweb.com.au/Reports/Current/Bidmove_Summary/) |
| Regex   | `PUBLIC_BIDMOVE_SUMMARY_([0-9]{8})_[0-9]{16}.zip`            |
| Example | [http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip](http://nemweb.com.au/Reports/Current/Bidmove_Summary/PUBLIC_BIDMOVE_SUMMARY_20170201_0000000280589268.zip) |
| File    | A single `csv` file (e.g. [PUBLIC_BIDMOVE_SUMMARY_20190428_0000000307275793.CSV](../assets/PUBLIC_BIDMOVE_SUMMARY_20190428_0000000307275793.CSV)) after decompression |
| Content | Two parts:<br> 1. [`BIDDAYOFFER_D`](../assets/BIDDAYOFFER_D.pdf) (about 1047 rows) summarises generator bids per day<br> 2. **[`BIDPEROFFER_D`](../assets/BIDPEROFFER_D.pdf)** summarises generator bids per period |
| Update  | daily shortly after 4am                                      |



### 2. Regional Load (5 min prediction)

| Aspect  | Description |
| ------- | ----------- |
| URL     |             |
| Regex   |             |
| Example |             |
| File    |             |
| Content |             |
| Update  |             |
|         |             |

### 3. Interconnector Connectivity & Limits

[http://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Congestion-Information/2017/Interconnector-Capabilities.pdf](http://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Congestion-Information/2017/Interconnector-Capabilities.pdf) 

### 4. Generator Ramp Rates

### 5. Loss Factors

url: https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Security-and-reliability/Loss-factor-and-regional-boundaries

A single `xlsx` file ([2018-19 MLF Applicable from 01 July 2018 to 30 June 2019 - updated 11 July 2018.xlsx](../assets/2018-19 MLF Applicable from 01 July 2018 to 30 June 2019 - updated 11 July 2018.xlsx)) has five sheets for five regions. Each sheet contains three parts:

1. Loads:

| Name        | Data Type | Mandatory | Comment                                       |
| ----------- | --------- | --------- | --------------------------------------------- |
| Location    |           |           |                                               |
| Voltage(kV) |           |           |                                               |
| TNI         |           |           | Connection point Transmission Node Identifier |
| 2018-19 MLF |           |           | Present Margional Loss Factor                 |
| 2017-18 MLF |           |           | Former Margional Loss Factor                  |

2. Generators:

| Name                | Data Type | Mandatory | Comment                                       |
| ------------------- | --------- | --------- | --------------------------------------------- |
| Location            |           |           |                                               |
| Voltage(kV)         |           |           |                                               |
| DUID                |           |           |                                               |
| Connection Point ID |           |           |                                               |
| TNI                 |           |           | Connection point Transmission Node Identifier |
| 2018-19 MLF         |           |           | Present Margional Loss Factor                 |
| 2017-18 MLF         |           |           | Former Margional Loss Factor                  |

3. Embedded Generators: same as above

**updates** annually by 1 April.

### 6. Market Price Cap

see [https://www.aemc.gov.au/news-centre/media-releases/aemc-publishes-schedule-reliability-settings-2018-19](https://www.aemc.gov.au/news-centre/media-releases/aemc-publishes-schedule-reliability-settings-2018-19)

| VALUES                     | 2017-18     | 2018-19         |
| -------------------------- | ----------- | --------------- |
| MARKET PRICE CAP           | $14,200/MWh | **$14,500/MWh** |
| CUMULATIVE PRICE THRESHOLD | $212,800    | $216,900        |

**updates** annually.

### 7. Actual Generation and Load Data

url: [http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/](http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/)

regex: `PUBLIC_DISPATCHSCADA_([0-9]{12})_[0-9]{16}.zip`

eg: `http://www.nemweb.com.au/REPORTS/CURRENT/Dispatch_SCADA/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.zip`

A single `csv` file (e.g. [PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.CSV](../assets/PUBLIC_DISPATCHSCADA_201904291630_0000000307295427.CSV)) after decompression: [`DISPATCH_UNIT_SCADA`](../assets/DISPATCH_UNIT_SCADA.pdf)

see [https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Market-Management-System-MMS/Generation-and-Load](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Market-Management-System-MMS/Generation-and-Load)

**updates** every five minutes.

### 8. Network Outages

url: [http://nemweb.com.au/Reports/Current/Network/](http://nemweb.com.au/Reports/Current/Network/)

regex: `PUBLIC_NETWORK_([0-9]{14})_[0-9]{16}.zip`

eg: `http://nemweb.com.au/Reports/Current/Network/PUBLIC_NETWORK_20190422133005_0000000307021827.zip`

A single `csv` file (e.g. [PUBLIC_NETWORK_20190429133006_0000000307290523.CSV](../assets/PUBLIC_NETWORK_20190429133006_0000000307290523.CSV)) after decompression contains two parts:

1. [`NETWORK_OUTAGECONSTRAINTSET`](../assets/NETWORK_OUTAGECONSTRAINTSET.pdf) lists the Constraint Sets that are expected to be invoked for the outage once it is confirmed to proceed
2. [`NETWORK_OUTAGEDETAIL`](../assets/NETWORK_OUTAGEDETAIL.pdf) lists asset owners planned outages for transmission equipment.

**updated** every 30 minutes, each day has 24 files

### 9. [Transmission Equipment Ratings](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings)

**`altlimits.zip`**: complete list of ratings used in AEMO's EMS (energy management system), **updated** when the network model is updated (normally every two weeks)

url: [http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip](http://nemweb.com.au/Reports/Current/Alt_Limits/altlimits.zip)

A single `csv` file (`⁨Eterra⁩/⁨habdata98⁩/⁨LimitData/altlimits.csv⁩`) after decompression

| Name            | Data Type   | Mandatory | Comment                                                      |
| --------------- | ----------- | :-------- | ------------------------------------------------------------ |
| Site Name       |             |           | The Substation, Terminal Station, or Power Station name      |
| Plant Type      | VARCHAR(10) |           | Transmission Lines may be Line, Tie, Summ for summated lines, or S_REACT for series reactors. Transformers may be Trans, Tx, or Tf. |
| Plant ID        | VARCHAR(20) |           | The equipment identifier                                     |
| Region          | VARCHAR(10) |           | The NEM region                                               |
| Measurement     |             |           | All values included in the publication process are MVA quantities |
| Level           |             |           | NORM, EMER, or LDSH as described in [Rating Application Levels](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Rating-Application-Levels) |
| Alternate Value |             |           | An identifier which describes when the rating is applicable, such as summer, winter, etc. Alternate Value application rules at the time of publication of this document are described in section 3 below. Note that any rating with an associated Alternate Value suffix of '_DYN' has a real time telemetered rating supplied by the asset owner. This telemetered value would normally be the rating applied in real time processes. If telemetered data is available, any associated static ratings will be used for predispatch, and for dispatch only on telemetered data failure. |
| Low             |             |           | The low and high provide a directional feature in the application of the rating. When associated with the Site Name, the Low and High are interpreted using the convention of : A positive value is power flow from the Site into the equipment. |
| High            |             |           | Same as above                                                |

**`PUBLIC_TER_DAILY.zip`**: contains the ratings used in constraint equations and the ID used in the right-hand of the constraint equations, **updated** on change (generally every few minutes) 

url: [http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip](http://nemweb.com.au/Reports/Current/Alt_Limits/PUBLIC_TER_DAILY.zip)

A single `csv` file (`⁨PUBLIC_TER_DAILY.csv⁩`) after decompression 

| Name            | Data Type   | Mandatory | Comment                                                      |
| --------------- | ----------- | :-------- | ------------------------------------------------------------ |
| SITE ID         |             |           | The Substation, Terminal Station, or Power Station name      |
| EQUIPMENT TYPE  | VARCHAR(10) |           | The type of equipment. Valid values are: LINE = Line  TRANS = Transformer
CB = Circuit breaker
ISOL = Isolator
CAP = Capacitor
REAC = Reactor
UNIT = Unit |
| EQUIPMENT ID    | VARCHAR(20) |           | The equipment identifier                                     |
| Region ID       | VARCHAR(10) |           | The NEM region                                               |
| RATING LEVEL    | VARCHAR(10) |           | NORM, EMER, or LDSH as described in [Rating Application Levels](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Rating-Application-Levels) |
| ALTERNATE VALUE |             |           | An identifier which describes when the rating is applicable, such as summer, winter, etc. Alternate Value application rules at the time of publication of this document are described in section 3 below. Note that any rating with an associated Alternate Value suffix of '_DYN' has a real time telemetered rating supplied by the asset owner. This telemetered value would normally be the rating applied in real time processes. If telemetered data is available, any associated static ratings will be used for predispatch, and for dispatch only on telemetered data failure. |
| RATING          |             |           | The rating value. Positive values indicate power flow from the site into the equipment. |
| RATING TYPE     |             |           | Either STATIC or DYNAMIC. Ratings with the Rating Type of DYNAMIC have a real time telemetered rating value supplied by the asset owner. This report does not include the telemetered rating value in the Rating field. The dynamic rating value would normally be the rating applied in Dispatch (and in some cases for a number of Pre-dispatch intervals). |
| SPD ID          | VARCHAR(21) |           | The identifier used in a constraint equation RHS to reference the rating value |
| EFFECTIVE FROM  | DATE        |           | The date and time the rating is active from and available as an input to constraint equations (inclusive) |
| EFFECTIVE TO    | DATE        |           | The date and time the rating is made inactive and unavailable as an input to constraint equations (exclusive) |

The above two tables describe the equipment identifiers, see [http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Equipment-Identifiers).