fif(and(b,d), conclusion(result)).
t! fif(and(b,d), conclusion(result2)).
t! if(and(b,d), result3).

bif(and(not(p(X,Y)), not(d(X))), a).
t! bif(and(not(q(X,Y)), not(d(X))), a).

if(and(if(not(t(x)), t(B)), atom), thing).
t! if(and(if(not(t(x)), t(B)), atom), thing).

b.
d.
