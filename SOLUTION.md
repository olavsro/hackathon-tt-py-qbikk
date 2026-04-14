# Explanation of the submission
 
## Solution



## Coding approach

How did the team arrive at the solution?


roadmaps først utifra premade prompts

parser kjører først.
-stripper kommentarer
-fjerener unødvendig space
-ser etter klasser og lagrer de basert på ending {}
-går igjennom klassene og ser etter metoder eller properties (private)
-lagrer metodene til neste steg


codegen:
-går gjennom hver metode og oversetter biter av de
-gjør metoder til def
-camelcase til snake case
-type mapping så array[] til list[]
-gjør om alle små expressions
	-this til self
	-arrow til lambda

transelator:
-hardcoded helper inntil videre på noen småting som ikke fungerer
-hardcoder metoder


spesifiserte ikke at den skal være generell. driver å hardcoder shit.


