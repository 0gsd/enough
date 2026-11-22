-- This file is read as text only, by enough's Lean reader (enough/lean_reader.py), and is never built.
/-
Written for enough's tests, 2026-11-22. Released under the licence of the repository.
Each piece of syntax the reader must get right stands here once. Nothing here is a real proof.
-/
module

public import Mathlib.Data.Nat.Basic
import all Mathlib.Logic.Basic

/-!
# Cases for the Lean reader

A module note. /- A nested comment -/ stays inside it.
-/

universe u

namespace Reader.Cases

open Nat hiding add_comm

section Strings

/-- A string with escapes, and an interpolated string; neither holds a use. -/
def greeting (n : ℕ) : String :=
  "say \"hi\" -- not a comment /- nor this -/" ++ s!"n = {n} and {"inner"}"

/-- A prime in a name, against a character literal. -/
def letter' (c : Char := 'a') : Char :=
  if c = '\'' then 'b' else c

end Strings

/-- A guillemet name, and Unicode names with subscripts. -/
def «odd name» (χ₈ : ℕ) : ℕ := χ₈ + 1

theorem hp₁_le {a b : ℕ} (hp₁ : a ≤ b) : a ≤ b + 1 := Nat.le_succ_of_le hp₁

/-- Strict-implicit binders. -/
theorem uses_strict ⦃a b : ℕ⦄ (h : a ≤ b) : a ≤ b + 1 := hp₁_le h

theorem _root_.top_level : True := trivial

theorem uses_top : True := top_level

namespace Inner.Deep

theorem deep_fact : 1 + 1 = 2 := rfl

end Inner.Deep

theorem uses_deep : 1 + 1 = 2 := Inner.Deep.deep_fact

namespace Other

theorem other_fact : 2 = 2 := rfl

end Other

open Other in
theorem uses_other : 2 = 2 := other_fact

namespace Left
theorem twin : True := trivial
end Left

namespace Right
theorem twin : True := trivial
end Right

open Left Right in
theorem uses_twin : True := twin

/- A structure and an inductive: the names they make. -/
structure Point where
  mk' ::
  x : ℕ
  y : ℕ := 0

inductive Colour where
  | red
  | green (shade : ℕ)

theorem point_x (p : Point) : p.x = p.x := rfl

theorem red_ne : Colour.red ≠ Colour.green 0 := by
  intro h
  cases h

variable {n : ℕ} (hn : 0 < n)

include hn in
theorem pos_succ : 0 < n + 1 := Nat.succ_pos n

omit hn in
@[simp]
private theorem helper : n + 0 = n := by simp

theorem uses_helper : n + 0 = n := helper

@[deprecated uses_helper (since := "2026-11-22")]
alias old_name := uses_helper

alias ⟨forward, backward⟩ := Nat.succ_le

@[to_additive add_twice]
theorem mul_twice (a : ℕ) : a * 1 = a := Nat.mul_one a

@[to_additive]
theorem mul_once (a : ℕ) : 1 * a = a := Nat.one_mul a

set_option linter.unusedVariables false in
theorem with_option (unused : ℕ) : True := trivial

mutual
  def evenish : ℕ → Bool
    | 0 => true
    | k + 1 => oddish k
  def oddish : ℕ → Bool
    | 0 => false
    | k + 1 => evenish k
end

axiom an_axiom : ∀ m : ℕ, m = m

theorem not_yet : 2 + 2 = 4 := by
  sorry

theorem by_machine : 2 + 2 = 4 := by
  native_decide

-- A run of line comments
-- is one comment.
theorem term_proof (a : ℕ) : a = a :=
  same a  -- an inline comment inside a declaration
where
  same (b : ℕ) : b = b := rfl

theorem tactic_proof (a b : ℕ) (h : a = b) : b = a := by
  obtain rfl := h
  rfl

end Reader.Cases
