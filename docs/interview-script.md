# Interview script: utility and installers (10 questions)

Owner: Mithil Rajapakse. Written: 11 Nov 2026.
Used for: November research stage (see `project-pipeline.md`, tasks R1 and R5).
Target: 1 utility person (CEB or LECO) and at least 2 installers by Fri 27 Nov. Four interviews (2 and 2) is better.
Time: 30-40 minutes. Ask Mithil to lead, someone else takes notes.

## Before the interview (10 minutes)

1. Send a short message: who we are, what the project is in one sentence, how long it will take, and that we ask no personal or customer details.
2. Ask permission to take notes. Ask permission before any recording. If they say no, take notes only.
3. Have a printed one-page summary of the proposal ready.
4. Read the question tags:
   - **U** = ask the utility person.
   - **I** = ask installers.
   - **B** = ask both.

## Opening (2 minutes, say it out loud)

"We are students at Curtin Colombo. We are building a small box and software that watches home solar systems and helps homes and the grid. We want to learn how things really work today. We will not share your name or company without your permission. May we take notes?"

## The 10 questions

Ask in this order. If time is short, ask the starred ones (**\***) first.

### 1. B: The rule change \*
"Since 11 September, new rooftop connections can only use Net Plus. What has changed for you since then? What are customers asking? What do you expect to happen with the appeal?"
Why: tells us if our savings story still holds and how stable the rules are.
Listen for: how many new applications, what customers choose now, any signs the rule will reverse.

### 2. I: What you actually install \*
"Think of your last 20 home installations. How many used each inverter brand and model? How many were single-phase and how many three-phase? What sizes (3, 5, 10 kW)? How many had batteries?"
Utility version (U): "From the applications you hold, which inverter makes and sizes are most common? Could you share anonymised counts by make and size?"
Why: there is no public brand share (`inverter-landscape-sri-lanka.md`).
Write down the actual numbers.

### 3. B: Getting data from the inverter
"If we want to read data from a home inverter, what is the easiest and most reliable way for each of your common brands? Who holds the installer password? Does connecting a third-party device affect the warranty?"
Why: decides how the Edge Unit connects.

### 4. U: Transformer and feeder problems \*
"Where and when do you see overloads or high voltage? How many feeders or transformers are limited today? How do you find out: customer complaints, field readings, or monitoring? What data would you want that you do not have now?"
Why: shows the grid problem is real and what the dashboard must show.

### 5. U: Inverter settings and compliance \*
"After the February 2025 blackout, the new protection settings were required. The regulator reports fewer than half of installed capacity has them. How do you check settings today? Would a tool that reads the settings and reports which homes comply be useful? Who would act on that report?"
Installer version (I): "How often do you see wrong or missing settings on site? Who changes them? How long does it take?"
Why: tests our strongest feature (the settings check).

### 6. B: Price and who pays \*
"A monitoring box would cost roughly US$ 70-95 in parts today. What would a household pay for it? Should the household, the installer, or the utility pay? What would make you recommend it or refuse it?"
Why: tests the cost we chose against reality.

### 7. I: Faults and service calls
"What are the three most common faults or service calls? How do you find out about a problem today? How many of your visits could have been avoided if you saw the data first?"
Utility version (U): "What are the most common rooftop-solar complaints you receive?"
Why: shapes the alert rules (fault-detect).

### 8. U: Visibility, data and permission
"If a third party sent you hourly data from a small number of homes, would you accept it? In what format? How often? What privacy rules apply? What approvals do we need to run a pilot on 2-5 homes in Colombo and Gampaha? Who signs?"
Installer version (I): "Would you install and support the box for a pilot? What would you need from us (training, a manual, a warranty statement)?"
Why: the pilot permission path is the biggest hidden risk.

### 9. B: Control and safety \*
"Today our pilot homes would be read-only. Later we may want to limit export or schedule a battery. Would you accept a third-party device changing inverter or battery settings? Under which rules? What must never be allowed?"
Why: decides the scope (`scope-decision.md`).

### Extra questions added 11 Nov (from `facts-check.md` and the grid simulation)

Ask these if there is time. Each one fills a gap we found.

- **U, with question 1:** "The PUCSL battery tariff (LKR 45.53) only covers systems above 250 kW. Is a tariff for home batteries expected in the next review? What would the operator need to see from small batteries first?"
- **U, with question 1:** "Which date decides the scheme: the application, the grid clearance, or the connection? We have seen both 11 September and 5 March 2026 reported."
- **U, with question 2:** "CEB reported about 109,000 rooftop connections at the end of 2025. PUCSL reported about 129,000 in September 2025. Is the difference LECO?"
- **U, with question 4:** "For a typical neighbourhood in Colombo or Gampaha: what transformer size, how many homes on it, what conductor, how long is the line, and what tap setting? How much rooftop solar do you allow on one transformer?" (These replace the assumptions in `grid-sim/README.md`.)
- **I, with question 7:** "How often do inverters switch off at midday because the voltage is too high? What do you do about it?"

### 10. B: The risk question and next people
"What is the biggest reason this project could fail? What would make you say no? Who else should we talk to? Is there any anonymised data (feeder load, inverter counts) you can share?"
Why: catches what we have not thought of and opens the next door.

## Close (2 minutes)

1. Say thank you.
2. Confirm what we may quote and how to name them (for example "a distribution utility engineer", not a name).
3. Ask if we can come back with the draft concept paper for comments in mid-December.
4. Say when they will hear from us next.

## After the interview (30 minutes, same day)

1. Fill in the note sheet below and save it in `docs/interviews/` as `YYYY-MM-DD-utility-or-installer-N.md`.
2. Remove names, phone numbers, emails, customer details and addresses. (`CONTRIBUTING.md` says no personal contact details in the repo.)
3. Pull out three things: numbers, surprises, and anything that changes the plan.
4. Post the three things in the team chat.

### Note sheet template

```
Date:
Who (role and organisation type only):
Interviewer / note-taker:
Recording? yes/no

Q1 Rule change:
Q2 Inverter counts (write the numbers):
Q3 Data access:
Q4 Feeder problems:
Q5 Settings and compliance:
Q6 Price and who pays:
Q7 Faults and service calls:
Q8 Data, permission, pilot path:
Q9 Control and safety:
Q10 Risks, next people, data offered:

Surprises:
Changes to our plan:
Follow-ups (who / by when):
```

## Done when

- At least 3 interviews done (1 utility and 2 installers), notes filed, and the three takeaways posted.
- Inverter counts from at least 2 installers are written in `inverter-landscape-sri-lanka.md`.
- We know what approval a 2-5 home pilot needs and who signs it.
