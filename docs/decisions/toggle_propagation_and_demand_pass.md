# Toggle propagation, demand propagation, and why there is no fixed point

- Date: 2026-09-21
- Kind: **decision record.** Immutable. Supersessions to it are recorded forward.
- Precondition for: output-contract respec §11 item 4, the realization layer signature.
- Supersedes, forward-only: the storage model bundle review's framing of demand
  propagation under toggles as a **fixed-point solve**. That framing is not edited
  where it stands; §6 below records what replaces it and why.

## 1. The question

Respec §4.4, restated verbatim in the 2026-09-21 handoff as open item 5:

> Underclocking a lane lowers upstream demand, which can drop an upstream machine
> and move its overflow discontinuously. Whether a set of toggles can oscillate is
> not demonstrated and not ruled out.

The handoff placed the argument *with* the signature rather than after it, on the
grounds that the fixed-point solve is the inflow half's core and the argument is
cheaper before it is written. That judgement holds, and for a sharper reason than
cost: the argument removes the fixed point.

## 2. Reduction — the state is an integer vector

Everything the realization layer emits for a given toggle configuration is a
function of one object: the per-lane machine-count vector

    m ∈ ℕ^L,  L = the set of lanes in the declared scope

Clock, power, input draw, overflow rate, storage size and the §6 projection are all
derived from `m` and from the demand vector `D`, and `D` is itself derived from `m`.
So any oscillation must appear as a cycle in the iterates of a map on ℕ^L. That is
the object to reason about; the real-valued rates are not.

Per lane L, with `r` the per-machine output rate of its recipe at 100% clock:

    m_L      = ceil(D_L / r)                       both policies
    STORE    clock 100%, output m_L · r, overflow m_L · r − D_L
             input draw per input item a:  m_L · a
    EXACT    clock D_L / (m_L · r) ≤ 1, output D_L, overflow 0
             input draw per input item a:  (D_L / r) · a

The two policies differ only in the input draw and the clock. Machine count is the
same expression under both — which is §4.2's geometry-invariance claim, and it is
visible directly in the two lines above rather than argued.

## 3. Result 1 — no outer loop exists

The oscillation in the question is of the form: *A off reduces B's demand, B drops a
machine, B's overflow falls, which changes A's feasibility.* For that to cycle,
something must **re-decide a toggle in response to the solve.**

Nothing does. Respec §4.6 settles the toggle as manual and states the reason —
wanting a buffer of something that is consumed downstream is a legitimate position
the tool is not entitled to overrule. The tool reports the consumed-downstream /
dead classification and takes the instruction. The toggle vector is therefore a
**declared input** to the map, not a variable of it.

So the feedback path the question describes is not present by construction. A toggle
configuration selects one map; it is not chosen by one.

This does not make the question empty — it relocates it. What remains is whether the
map *for a fixed toggle configuration* terminates. §§4–5.

## 4. Result 2 — on an acyclic credited flow, one reverse pass, no iteration

Order the lanes by material flow. Lane L's demand is

    D_L = (external target for item_L)  +  Σ  input draw for item_L by consumers of L

Both input-draw expressions in §2 depend only on `D` at the **consuming** lane. So
`D_L` is fully determined by lanes downstream of L, and by nothing upstream.

If the flow graph is acyclic, a single traversal in reverse topological order —
final outputs first, raw extraction last — assigns every `D_L` and every `m_L`
exactly once. There is no iteration to converge, and therefore nothing to oscillate.

This holds **for every toggle configuration**, and for mixed ones. The toggle changes
which of the two input-draw expressions is used at a lane; it does not change the
direction of the dependency. It also holds under lane decomposition (respec §5):
lane count and per-lane machine count are both functions of `D_L` and the trunk
capability, so decomposition is evaluated inside the same single visit.

**The discontinuity in §4.4 is real and is not a termination problem.** Dropping an
upstream machine moves that lane's overflow by up to a full machine's output — the
storage review measured up to 12.5× on one notch. That is a sawtooth in the
*output* as a function of the scenario axis. It is not a cycle in the computation,
because the computation visits each lane once.

## 5. Result 3 — cyclic credited flow is where the risk actually lives

The acyclicity in §4 is of the **credited** flow graph, not of the recipe graph.
Crediting a byproduct against demand adds an edge from the producing lane to every
consumer of that byproduct. A cycle appears exactly when an item is a byproduct of a
recipe that transitively consumes it.

On such a cycle the map is **not monotone**, and this is the substantive finding:

    m_L = ceil(D_L / r)                is monotone non-decreasing in D_L
    input draw, both policies          is monotone non-decreasing in D_L
    overflow = m_L · r − D_L           is NOT monotone in D_L

Overflow is a sawtooth: decreasing within a machine step, jumping up at each
boundary. Credited against demand elsewhere, it enters the map with a negative sign
and destroys monotonicity. Without the credit the map is monotone on a bounded
integer box — `m` is bounded above whenever the declared resource caps bound
throughput, and an unbounded `m` means the scope is infeasible and the solve already
fails — so iteration from `m = 0` gives an ascending chain that terminates at the
least fixed point in at most Σ m_max steps. With the credit, that argument is not
available, and no replacement for it is offered here.

**This is a pre-existing condition, not one the toggle introduces.** It is the
standing defect already on the handoff's list — *`_demand_oracle` credits no
byproducts; invalid where one feeds back.* The toggle makes it more visible, because
underclocking scales byproduct output continuously, but the cycle is a property of
the recipe set and the credit rule.

**Guard, and it is the existing one.** Detect the cycle in the credited flow graph
and refuse, naming the item. This is the same shape as `AmbiguousDemand` — the layer
declines rather than returning a number it cannot stand behind, which is §8.1's
general form applied to a termination condition instead of to a preference.

For the record, the uncredited linear case has a classical name: with EXACT
everywhere and no `ceil`, the system is Leontief demand propagation and convergence
on a cyclic graph is the Hawkins–Simon condition on the technology matrix. The
`ceil` is a monotone perturbation bounded by one machine per lane, so it does not
break that case. Naming it is not a proof of the credited case and is not offered as
one.

## 6. Decision

    DECIDED   the demand pass is a SINGLE traversal in reverse topological order
              of the credited flow graph. It is not a fixed-point iteration and
              carries no convergence tolerance and no iteration cap.
    DECIDED   a cycle in the credited flow graph is detected before the traversal
              and REFUSED by name. It is not iterated toward.
    DECIDED   the toggle vector is an input to the pass. The layer never selects,
              adjusts or re-runs against a toggle it chose.

This is a narrowing of the storage review, which specified a fixed-point solve. That
document is not edited. What it anticipated is correct in outline — the demand under
toggles does have to be re-derived through the chain — and wrong in mechanism: it
assumed iteration because it did not separate the acyclic case, which is the whole
of the current scope, from the credited-cycle case, which is refused.

## 7. What this does not establish

    not shown   that the credited-cycle case terminates under any iteration
                scheme. It is refused, not solved.
    not shown   that the declared scope is in fact acyclic in its credited flow.
                The refusal check makes this observable per solve rather than
                assumed; it has not been run against the scenario of record.
    not shown   how machines are distributed across lanes when a group needs
                more than one. Even-split and fill-then-spill give DIFFERENT
                total round-ups — even-split rounds up to once per lane,
                fill-then-spill once per group — so this changes the storage
                residual and is a live question, not a formatting choice.
                Respec §5 consequence 2 reads as even-split; §4.3's averaging
                argument pulls toward spreading across the whole group. Open.
    not shown   that `m` is bounded in practice. The argument assumes the
                declared caps bind; an uncapped raw input makes the box
                unbounded and the monotone argument in §5 vacuous, though the
                §4 acyclic result does not depend on it.
    unread      whether `progression/unlocks.py` or `progression_clusters.csv`
                already resolves a logistics capability to a numeric tier.
                That store was not checked in this session.

## 8. Consequence for the signature

The realization layer needs no solver, no tolerance, no iteration cap and no
convergence warning. It needs a topological sort, a cycle check, and one visit per
lane. That is a smaller object than the storage review's framing implied, and it is
the shape the signature is written to.

---

## Amendment 1 — 2026-09-21

Appended the same day, forward-only. Sections 1-8 above are not edited. Three
corrections and one supersession, all from the same session.

### A1.1 Section 7 conflated two different axes — corrected

Section 7 records the split rule as open and says section 4.3's averaging
argument "pulls toward spreading across the whole group." That is wrong, and
the reason matters.

Power at fixed output is

    P_total = P_base * (D/r)^e * N^(1-e)        e = 1.321929 > 1

which is **strictly decreasing in machine count N, without bound**. So
"minimise power" always answers *more machines* and has no interior optimum.
Measured on section 7's example, 290 ingot/min against 30/min producers:

    N=10  clock 96.7%   38.25 MW
    N=12  clock 80.6%   36.07 MW
    N=16  clock 60.4%   32.88 MW

Section 4.3's Jensen argument is valid for distributing clock across a FIXED
machine set — averaged versus split within a lane, which is what it settled —
and does not extend to choosing the set. Even-split's lower power is a
consequence of having more machines, not evidence that it is the better rule.
Power cannot break this tie.

### A1.2 Fill-then-spill is dominated — narrowed

Section 7 offered even-split and fill-then-spill as the two candidates. A third
construction — minimum total machines, balanced across lanes, one clock —
dominates fill-then-spill on every axis at that example:

                            machines  overflow(STORE)  power(EXACT)  clocks
    fill-then-spill [4,4,2]    10        10/min         38.29 MW      two
    min-machines    [4,3,3]    10        10/min         38.25 MW      one

Equal or better throughout, and one clock setting rather than two.
Fill-then-spill comes off the list.

### A1.3 The remaining question is superseded, not answered

Both surviving candidates assume a lane belongs to one product. It does not.
Shared intermediates make the primitive a BUS — (item, producer set, consumer
set) — and backpressure redistributes surplus across a bus's consumers before
anything is stored. Per-lane overflow is therefore not a physical quantity, and
the even-split-versus-balanced question as section 7 poses it is asked about
the wrong object.

    SUPERSEDED  section 7's open item on machine distribution across lanes.
                See docs/decisions/bus_allocation_backpressure_and_residual.md,
                which replaces the lane with the bus and moves the residual
                to it.

### A1.4 Sections 1-6 stand

Nothing here touches the termination result. Toggles remain declared inputs
rather than variables; the credited-flow traversal remains a single reverse-
topological pass; the credited-cycle case remains refused rather than iterated
toward. Moving from lanes to buses changes what a node in that traversal IS,
not that the traversal terminates — a bus has the same property section 4
relies on, that its demand depends only on its consumers.

One clarification the bus model forces: section 2's reduction to the integer
vector m in N^L is now indexed by BUSES, not lanes, and D_L is the bus's total
consumer draw. The argument is unchanged; the index set is renamed.
