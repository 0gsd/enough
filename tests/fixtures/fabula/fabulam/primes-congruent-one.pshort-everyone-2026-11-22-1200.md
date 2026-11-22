# primes-congruent-one, for everyone

*A pshort of primes-congruent-one.fabulam.cosm at everyone. It is a guide to a formal proof. It is not a proof.*

*The file's text holds no `sorry` and declares no axiom of its own. It was read here as text. Nothing was built or run, so whether Lean accepts it is not known here.* [P:claim/checking]

Fix a whole number other than zero; call it k. The statement: for every such k, infinitely many primes, numbers that only one and themselves divide, leave a remainder of one when divided by k. It is enough that beyond any number you name, call it n, one more such prime can be found. [N:aim/infinitely-many-primes-one-mod-k, C:statement/Nat.infinite_setOfPred_prime_modEq_one, C:part/one-beyond-every-bound]

For k above one, multiply k by n factorial, the product of every whole number from one to n; call the result b. Feed b into a fixed formula built from its powers, the k-th cyclotomic polynomial: because k is above one, the outcome is larger than one. Its smallest divisor other than one, call it p, is prime, and counted by remainders on division by p, the formula at b leaves nothing over. [C:part/the-candidate-prime]

By the way the formula is built, p cannot divide b. Yet b is a multiple of every number from one to n, so p is none of them and lies beyond n. [C:part/past-the-bound]

Multiplying b by itself again and again, keeping only remainders on division by p, first returns to one after exactly k rounds. Such a cycle fits a whole number of times into one less than p, so p leaves remainder one when divided by k. This needs p not to divide k, which holds because k divides b and p does not. [C:part/order-exactly-k]

A worked case: take k as 3 and n as 2. Then b is 3 times 2 factorial, which is 6, and the third formula, a number squared plus that number plus one, gives 43 at 6. As 43 is prime, p is 43, beyond 2. Next, 43 minus 1 is 42, which is 3 times 14, so 43 leaves remainder one when divided by 3; and 6 cubed is 216, which is 5 times 43 plus 1, so 6 returns to one after exactly 3 rounds. [P:case/three-and-two]

When k is one, the remainder asks nothing, so any prime beyond n will do, and the old fact that primes never run out supplies one. [C:part/the-modulus-one]

One such prime beyond every named number means meeting them again and again with no last one, and so endlessly many: that is the statement. [C:part/back-to-infinitely-many]

What the proof delivers: for each k other than zero and each n, one prime above n that leaves remainder one when divided by k. For k above one, that prime lies between n and the formula's outcome: above n, and at most the outcome. [P:yield/what-the-proof-delivers]

The file's text holds no `sorry` and declares no axiom of its own. It was read here as text; nothing was built or run, so whether Lean accepts it is not known here. [P:claim/checking]

Left open: the method reaches only the remainder one; for other remainders sharing no factor with k it says nothing. [C:statement/Nat.infinite_setOfPred_prime_modEq_one]

*a pshort of primes-congruent-one.fabulam.cosm, at everyone, entailed apart on 2026-11-22 by blind-entailer*
