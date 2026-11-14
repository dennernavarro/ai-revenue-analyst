# Stage 0 — Foundation (no LLM)

**Built:** canonical domain models, the `PMSProvider` protocol, a JSON-backed
`MockPMS` adapter, a booking-arrival simulator, and pure analytics functions
(occupancy, ADR, RevPAR, on-the-books as-of).

**Key decisions**

- *Simulate arrivals, don't invent occupancy.* Booking requests arrive with
  seasonality, lead time and length of stay; a request becomes a reservation
  only if a unit is free. Occupancy, pace and gaps all emerge consistently
  from one process, and bookings "made after" the simulated today (AS_OF)
  simply don't exist yet — which is what makes booking-pace questions real.
- *The provider contract is guarded by contract tests*, not documentation. A
  future real-PMS adapter is done when it passes the same suite the mock does.
- *As-of correctness:* `status` is the final state; pace questions use
  `booked_at`/`cancelled_at` timestamps instead.

**Takeaway:** an agent is only as debuggable as its tools. Getting a
deterministic, tested calculation layer first makes every later stage easier.
