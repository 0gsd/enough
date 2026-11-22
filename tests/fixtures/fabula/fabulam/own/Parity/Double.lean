-- Read as text only: enough wrote this file for its tests, and Lean never built it.
import Parity.Basic

namespace Parity

/-- The doubles of two numbers add to the double of their sum. -/
theorem double_add (a b : Nat) : 2 * a + 2 * b = 2 * (a + b) := by
  rw [Nat.mul_add]

end Parity
