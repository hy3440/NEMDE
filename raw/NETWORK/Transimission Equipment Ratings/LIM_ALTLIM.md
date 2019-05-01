# LIM_ALTLIM

| Name            | Data Type   | Mandatory | Comment                                                      |
| --------------- | ----------- | :-------- | ------------------------------------------------------------ |
| SITE ID         |             |           | The Substation, Terminal Station, or Power Station name      |
| EQUIPMENT TYPE  | VARCHAR(10) |           | The type of equipment. Valid values are: LINE = Line  TRANS = Transformer CB = Circuit breaker ISOL = Isolator CAP = Capacitor REAC = Reactor UNIT = Unit |
| EQUIPMENT ID    | VARCHAR(20) |           | The equipment identifier                                     |
| Region ID       | VARCHAR(10) |           | The NEM region                                               |
| RATING LEVEL    | VARCHAR(10) |           | NORM, EMER, or LDSH as described in [Rating Application Levels](http://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/Data/Network-Data/Transmission-Equipment-Ratings/Rating-Application-Levels) |
| ALTERNATE VALUE |             |           | An identifier which describes when the rating is applicable, such as summer, winter, etc. Alternate Value application rules at the time of publication of this document are described in section 3 below. Note that any rating with an associated Alternate Value suffix of '_DYN' has a real time telemetered rating supplied by the asset owner. This telemetered value would normally be the rating applied in real time processes. If telemetered data is available, any associated static ratings will be used for predispatch, and for dispatch only on telemetered data failure. |
| RATING          |             |           | The rating value. Positive values indicate power flow from the site into the equipment. |
| RATING TYPE     |             |           | Either STATIC or DYNAMIC. Ratings with the Rating Type of DYNAMIC have a real time telemetered rating value supplied by the asset owner. This report does not include the telemetered rating value in the Rating field. The dynamic rating value would normally be the rating applied in Dispatch (and in some cases for a number of Pre-dispatch intervals). |
| SPD ID          | VARCHAR(21) |           | The identifier used in a constraint equation RHS to reference the rating value |
| EFFECTIVE FROM  | DATE        |           | The date and time the rating is active from and available as an input to constraint equations (inclusive) |
| EFFECTIVE TO    | DATE        |           | The date and time the rating is made inactive and unavailable as an input to constraint equations (exclusive) |