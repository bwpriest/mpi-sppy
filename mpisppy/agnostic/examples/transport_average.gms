$title A Transportation Problem (TRNSPORT,SEQ=1)

$onText
This problem finds a least cost shipping schedule that meets
requirements at markets and supplies at factories.


Dantzig, G B, Chapter 3.3. In Linear Programming and Extensions.
Princeton University Press, Princeton, New Jersey, 1963.

This formulation is described in detail in:
Rosenthal, R E, Chapter 2: A GAMS Tutorial. In GAMS: A User's Guide.
The Scientific Press, Redwood City, California, 1988.

The line numbers will not match those in the book because of these
comments.

Keywords: linear programming, transportation problem, scheduling
$offText

Set
   i 'canning plants' / seattle,  san-diego /
   j 'markets'        / new-york, chicago, topeka /;

Parameter
   a(i) 'capacity of plant i in cases'
        / seattle    350
          san-diego  600 /

   b(j) 'demand at market j in cases'
        / new-york   325
          chicago    300
          topeka     275 /;

Table d(i,j) 'distance in thousands of miles'
              new-york  chicago  topeka
   seattle         2.5      1.7     1.8
   san-diego       2.5      1.8     1.4;

Scalar f 'freight in dollars per case per thousand miles' / 90 /;

Parameter 
   c(i,j) 'transport cost in thousands of dollars per case'
   cost_y(j) 'costpenalty of the slack penalty';
c(i,j) = f*d(i,j)/1000;
cost_y(j) = 20;

Variable
   x(i,j) 'shipment quantities in cases'
   z      'total transportation and slack costs in thousands of dollars'
   y(j)   'slack penalty for the demand not supplied';

Positive Variable x;
Positive Variable y;
x.up(i,j) = 1000;

Equation
   cost      'define objective function'
   supply(i) 'observe supply limit at plant i'
   demand(j) 'satisfy demand at market j';

cost..      z =e= sum((i,j), c(i,j)*x(i,j)) + sum(j, cost_y(j)*y(j));

supply(i).. sum(j, x(i,j)) =l= a(i);

demand(j).. sum(i, x(i,j)) + y(j) =e= b(j);

$onText
__InsertPH__here_Model_defined_three_lines_later
$offText

Model transport / all /;

solve transport using lp minimizing z;