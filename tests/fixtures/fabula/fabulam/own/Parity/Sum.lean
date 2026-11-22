-- Read as text only: enough wrote this file for its tests, and Lean never built it.
import Parity.Basic
import Parity.Double

/-!
# The sum of two even numbers

The sum of two even numbers is even.
-/

namespace Parity

/-- The sum of two even numbers is even. -/
theorem isEven_add {m n : Nat} (hm : IsEven m) (hn : IsEven n) : IsEven (m + n) := by
  obtain ⟨a, ha⟩ := hm
  obtain ⟨b, hb⟩ := hn
  exact ⟨a + b, by rw [ha, hb, double_add]⟩

end Parity
