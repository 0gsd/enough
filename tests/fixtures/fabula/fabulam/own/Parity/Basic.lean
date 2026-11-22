-- Read as text only: enough wrote this file for its tests, and Lean never built it.
/-!
# Even numbers

A natural number is even when it is twice a natural number.
-/

namespace Parity

/-- A natural number is even when it is twice some natural number. -/
def IsEven (n : Nat) : Prop := ∃ k, n = 2 * k

/-- Twice a number is even. -/
theorem isEven_double (k : Nat) : IsEven (2 * k) := ⟨k, rfl⟩

end Parity
