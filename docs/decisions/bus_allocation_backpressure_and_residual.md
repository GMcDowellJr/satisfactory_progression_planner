# Bus allocation, backpressure, and where the residual lives

- Date: 2026-09-21
- Kind: **decision record.** Immutable. Supersessions recorded forward.
- Governs: the realization layer's treatment of shared intermediates, storage,
  and splitter geometry. Written after `toggle_propagation_and_demand_pass.md`
  of the same date, which it does not edit; see the amendment appended there.
- Source: worked against `planning_data/game/reference/` at the scenario of
  record (1.25x parts / 2x power / 2x Space Elevator, game 1.2.4.0 CL#502094),
  with the in-game mechanics supplied by Greg in session and named as such in
  §9 rather than presented as derived.

## 1. The lane was the wrong primitive

The output-contract respec §5 defines a lane as a production block whose
throughput fits one belt, and treats downstream isolation per lane as the
object. Built out, that implies a *vertical slice* — a chain replicated from
raw material to product, isolated end to end.

That model does not survive contact with an ordinary factory. A starter base
makes Reinforced Iron Plate **and** Rotors, and both consume screws. The screw
producers are not a lane belonging to either; they are a **bus** with two
consumers. Nothing in the respec's vocabulary names that object.

Measured on the scenario of record, at one base assembler of each product:

    screw bus   199/min      RIP 75 (37.7%)     Rotor 124 (62.3%)

**The primitive is therefore the bus: (item, producer set, consumer set).**
Lane decomposition happens *inside* a bus's producer set — how many parallel
producer lines — and the bus emits a consumption partition. Whether a bus can
stay isolated is a property of its consumer set, not a design choice: one
consumer can be isolated, two or more must merge.

A figure computed under the slice model is void and is recorded here so it is
not re-quoted: a fully isolated vertical slice for Reinforced Iron Plate at
1.25x came to 226 machines and 2370 ingot/min internal flow. The arithmetic is
correct and the object is fictional — nobody builds a dedicated screw chain per
consumer. It is named because it was stated in session before the error was
found.

## 2. Backpressure is the allocation mechanism, not a policy

A splitter round-robins over outputs that can accept an item and skips a
blocked one. So a consumer that is satisfied backs up, the splitter stops
offering it items, and the surplus reaches the other consumers.

**Consequence: the topology does not need to encode the demand ratio.** In
steady state, any connected topology with adequate belt capacity converges to
each consumer's draw, provided total supply is at least total demand.

This is the manifold-versus-balancer question and it comes down on manifolds.

    satisfactory-logistics, 200 -> 75 / 125     6 splitters + 3 mergers = 9
    minimal exact tree, same split              3 splitters + 2 mergers = 5
    connected, relying on backpressure          1 splitter, merger optional

The nine-element tree atomises the stream into eight 25/min units and rebuilds
them. It is correct and it is solving a problem the steady state does not pose.

**Exactness earns its elements in exactly two cases:**

    deficit          supply < demand. Nobody backs up, so the nominal ratio
                     decides who starves. This is the case where adding one
                     producer removes the problem instead of solving it.
    path capacity    a branch whose belt Mk is below its consumer's draw
                     starves regardless of backpressure. A capability check
                     (respec §3's floor), not a topology one.

## 3. Residual is a property of the bus, not of a lane

Because backpressure moves surplus between consumers before anything can be
stored, **per-lane overflow is not a physical quantity.** Only

    R = supply − total bus demand

is real, where supply is the ceil'd producer count at full rate and demand sums
*every* consumer on the bus.

This retires respec §4.6's classification as a separate output. "Is this
overflow consumed downstream or dead" was specified as a report the player
consults before flipping the toggle. Backpressure makes consumed-downstream
surplus consumed automatically — it never reaches storage — so the distinction
is already inside the sum. What is left over is dead by construction.

**It also revises measured figures, not only the model.** The storage model
bundle review measured Stitched Iron Plate accumulating 22.5 wire/min. That was
taken per-lane. Wire has other consumers on its bus, so 22.5 is a pre-
backpressure figure and not a residual. Every per-lane overflow figure in that
document needs recomputing at the bus. That document is not edited; this is the
forward record.

## 4. Storage is a quantity and a disposition, not a boolean

R is quantised: at the ceil it is whatever rounding left, and it cannot be
increased except by a whole producer.

    R(k) = ceil_residual + k · producer_rate

Screw bus, producer 40/min, demand 199/min:

    machines  supply   R          producers at 100%   backing up   underclocked
      5          200    1.0/min      20.00 MW          19.90 MW     19.87 MW
      6 (+1)     240   41.0/min      24.00 MW          19.90 MW     18.74 MW
      7 (+2)     280   81.0/min      28.00 MW          19.90 MW     17.83 MW

At the ceil the bus yields **1/min** of storage. Wanting meaningful storage
means adding a machine, and the quantum is a full 40/min. So the storage rate
is declared as a producer count, and the old per-item boolean cannot express it.

Three things in that table that the boolean was hiding:

**Backing up is flat in machine count.** 19.90 MW at five, six or seven
producers. With no drain, power is a function of throughput alone and extra
producers merely idle more. Building past the ceil then costs build cost and
footprint and nothing in power, and buys nothing.

**Underclocking falls in machine count.** 19.87 → 18.74 → 17.83. Power is
convex in clock (exponent 1.321929 on all eleven producers), so spreading a
fixed output over more machines is strictly cheaper. This is the only column
where extra producers pay for themselves.

**Only running at 100% scales up.** 20 → 24 → 28, because the machines are
actually running.

The two axes are therefore independent and both are declared:

    quantity      extra producers beyond the ceil        default 0
    disposition   what happens to R                      see §5

## 5. The steady state, and why 100% is not one of them

**A storage container draws no power.** [stated, Greg]

**A container is a finite buffer.** When it fills, the producers feeding it
pause until it is drawn down. [stated, Greg] So "producers at 100% with R
accumulating" is a *transient* whose duration is container capacity divided by
R — after which the system reverts to the backing-up row of §4's table. The
fill dynamics are part of the game and are deliberately not modelled.

That leaves three steady states, distinguished by what drains R:

    BACK UP     no drain. Producers idle at utilisation demand/supply.
                Power linear in utilisation. No stock. Zero effort — this is
                what an unattended factory does by default.
    WITHDRAWN   the player drains the container. Producers run at 100% while
                it has room. Not a tool-side state: it depends on player
                behaviour, and §9's no-player-time rule keeps it out.
    SUNK        a smart splitter sends the main line to storage and the
                overflow to an AWESOME Sink. Producers never stop, power draw
                is CONSTANT, and the sink returns coupon points. [stated, Greg]

**Power stability is the reason the third one matters**, and it is a property
the current model cannot express. A factory whose producers oscillate between
running and paused presents a fluctuating draw, which has to be sized against
its peak; a sunk overflow presents a constant one. That bears directly on the
generator surface (respec §10.5) — headroom against a fluctuating load is a
real cost that a constant load does not pay.

**This gives handoff open item 8 a second reason to exist.** The AWESOME Sink's
absence from the reference layer was recorded as gating disposal mode. It also
gates the only steady state with stable power. Coupons are not a game driver
[stated, Greg] and are not modelled.

## 6. Two lattices, and they are not interchangeable

A demanded ratio has to land on something buildable, and there are two distinct
sets of buildable ratios.

**Partition the producer set** — with N producers the reachable shares are k/N,
at a cost of **zero elements**. Five screw constructors give fifths for free.

**Splitter tree** — a splitter divides by 2 or 3 and a merger adds, so every
reachable fraction has a **3-smooth denominator** (2^i · 3^j): halves, thirds,
quarters, sixths, eighths, ninths, twelfths. **Fifths are not reachable.**

So `2/5` exists only in the first lattice and `1/3` is cheap only in the
second, and the demanded 37.7% sits between them. On the screw bus:

                        RIP       Rotor    elements   machines
    2:3 machine split   100.0%     96.8%       0          5
    1/3 : 2/3            88.9%    100.0%       2          5
    3/8 : 5/8           100.0%    100.0%       5          5
    2:4 machine split   100.0%    100.0%       0          6

`3/8 × 200 = 75` exactly, and 8 is 3-smooth, so the exact split builds: halve
to 100/100, halve one to 50/50, halve one to 25/25; RIP takes 50+25, Rotor
takes 100+25.

The last row is the operative one: **one extra producer removes the problem**,
because it moves the free lattice rather than paying in the expensive one.

The 3-smooth claim holds for **acyclic** trees only. Feeding a stream back
upstream of a splitter reaches arbitrary rationals. Whether the tool should
ever emit a looped topology is not decided here.

## 7. What this does to respec §7.2

§7.2 records the splitter objective as two terms — fewest elements, fewest
crossings — with no stated trade-off, against an upstream that scalarises
nodes+edges at 1:1 and carries no crossing term. That understates it twice.

The objective has four terms, and the upstream carries one:

    throughput error   |achieved ratio − demanded ratio|     upstream: absent
    machine count      moves the free lattice                upstream: absent
    elements           nodes + edges                         upstream: 1:1
    crossings          planarity                             upstream: absent

And §2 removes most of the problem: the upstream solves *construct ratio R with
fewest elements*, which is the deficit case. In the supply-adequate case the
answer is to connect it and stop.

    DECIDED   the realization layer does not emit splitter topologies for
              ratio construction. It emits the bus partition as ratios
              (respec §5 consequence 3), plus three checks: supply ≥ demand,
              every branch's belt carries its draw, the bus is connected.
    DECIDED   a port from IceMoonMagic/Satisfactory-Splitter-Calculator is
              not undertaken on §7.2's stated grounds. If it is undertaken
              later it is for the deficit case specifically, and the four-term
              objective above is the thing to settle first.

## 8. Unlocks re-partition buses

An alternate recipe is not only a cheaper recipe; it is a **re-wiring event**.
Stitched Iron Plate removes Reinforced Iron Plate from the screw bus entirely.
Measured, targets held fixed at 5 RIP/min and 4 Rotor/min:

                       screw bus   partition              machines
    base RIP             199/min   RIP 37.7% Rotor 62.3%   19.02 → 20
    Stitched + Iron Wire 124/min   Rotor 100%              15.79 → 19

The bus sheds 37.7%; screw and rod each drop a producer; a two-machine Iron
Wire lane appears on the ingot bus.

**The integrality tax makes the alternate scale-dependent.** Regime B is 17%
leaner in continuous machine-equivalents and saves exactly one machine after
round-up — 3.21 machines of slack against 0.98. At one assembler of each the
alternate barely pays; the crossover scale is computable and is not computed
here.

    DECIDED   a realization report is valid for a RECIPE SET, and names the
              unlocks that would invalidate it. Derived from the consumer
              sets, declaration-shaped rather than an optimisation, so
              admissible under §8.1. No player time enters, so §9 holds.

## 9. Provenance of the mechanics

The following are **stated by Greg in session** and are game mechanics, not
derived from the reference layer or observed by the tool:

    - a splitter round-robins over unblocked outputs, so surplus redistributes
      to other consumers on the bus
    - storage containers draw no power
    - a full container pauses the producers feeding it
    - a smart splitter can route the main line to storage and the overflow to
      an AWESOME Sink, keeping producers running and the draw constant
    - sink coupons are not typically a game driver

They are load-bearing for §§2–5 and none is checked against the snapshot or
observed by this tool. If any is wrong, the affected section falls.

## 10. What this does not establish

    not shown   the crossover scale at which an alternate's leanness beats
                its integrality tax
    not shown   startup behaviour. Everything here is steady state, and fill
                time is the one real argument for a balancer in the
                supply-adequate case
    not shown   idle power draw. §4's "backing up" column assumes an idle
                producer draws ~0. A non-zero idle draw shrinks every gap in
                that column and was not verified against the reference layer
    not shown   whether the divisibility losses at 1.25x (smelter→plate moves
                from 1:1 to 4:3) are typical or particular to that pair.
                Computed for the iron chain only
    not run     the bus-level recompute of the storage review's per-lane
                overflow figures. Named as owed in §3 and not performed
    unread      whether progression/unlocks.py resolves a capability to a
                numeric tier. That store has not been checked
