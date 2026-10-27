# EventHub submission checklist

Application implementation is complete. Checked items have repository or executed
verification evidence; unchecked items still need group work or manual confirmation.
Assignment paragraph locators follow requirements.md. Do not invent contributions
or use real participant information in demonstration data.

## Code and repository instructions

- [x] Four complete production modules: main.py, events.py, bookings.py, storage.py.
- [x] All required menu workflows, capacity/FIFO promotion, reports and JSON reload.
- [x] Python 3.10+ syntax, standard-library runtime, functions and Ruff checks.
- [x] README setup/run instructions, menu, data path, first run and safety guidance.
- [x] Final requirements, architecture, data model and business rules reflect code.
- [ ] Optional additional assurance: execute under an actual local Python 3.10 runtime;
  local full tests used Python 3.12.14 and separate 3.10 syntax checks. CI targets 3.10.

## Testing and sample data

- [x] 579 automated tests pass: console 65, main 102, events 155, bookings 122,
  storage 131, imports 4. Ruff lint/format and git diff whitespace checks pass.
- [x] Normal registration; full capacity/FIFO waiting; cancellation/automatic promotion
  covered by a real console/storage integration test.
- [x] Final acceptance sequence exercised create/edit/list/search/register/promote,
  report/cancel/Exit/restart and persisted reload in isolation.
- [x] Original fictional `samples/eventhub.json` demonstrates active available seats,
  full event/ordered waiters and retained cancelled event without residual bookings.
- [x] Sample validated through actual storage, list/keyword/date/report APIs and
  isolated startup/console list/report; tracked sample remains unchanged.
- [ ] Capture final screenshots with expected/actual results and troubleshooting.
- [ ] Fresh-extraction/another-computer run of the actual final submission package.

## Group PDF — 5–10 pages (P84)

- [ ] Overview, requirements, design and final four-module program structure.
- [ ] Implemented data structures, algorithms, JSON safety and validation decisions.
- [ ] Test cases with screenshots/results, challenges and reproducible run instructions.
- [ ] Identifiable truthful contribution and technical explanation from every member.
- [ ] Verify final PDF readability, filenames and page count.

## Presentation and live demonstration (P71, P85–88)

- [ ] Final .pptx, 10–15 slides: problem/design/features/screenshots/tests/lessons.
- [ ] Rehearse 10–15 minute group presentation followed by instructor questions.
- [ ] Demonstrate normal registration, full event/waiting, cancellation/promotion
  and restart persistence using a safe working copy of fictional data.
- [ ] Every member speaks, identifies their contribution, explains the complete
  application and can answer questions. Attend compulsory live presentation.

## Group contribution record (P48, P54–55, P79–81)

- [ ] Confirm maximum four members; record actual names, student IDs and specific work.
- [ ] Record actual coding/testing/review/documentation/demo/presentation roles with
  evidence such as commits, review records, test outputs and authored sections.
- [ ] Confirm participation, collaboration and whole-application understanding.
- [ ] Identify each student's documentation contribution and speaking/demo role.
- [ ] Review rubric: shared code 5 marks; individual documentation 5; presentation 5.

## ZIP and Moodle (P49, P97–99)

- [ ] Include four source files, fictional sample JSON, README, final PDF and PPTX.
- [ ] Include useful tests, docs, pyproject.toml and requirements-dev.txt; CI workflow
  may accompany source but is not required to run the application.
- [ ] Exclude .git, virtual environments, caches, personal runtime data, secrets,
  temporary/damaged investigation files and irrelevant IDE files.
- [ ] Name ZIP `EventHub_<GroupID>.zip`, replacing GroupID with actual group student
  IDs (assignment example: `EventHub_12345_67890.zip`). Label files clearly.
- [ ] Inspect ZIP and run from a clean extraction; verify sample-copy instructions.
- [ ] Confirm Moodle deadline/presentation date/time and academic year with instructor.
  Assignment filename references Fall 2026/27; internal heading says Academic Year
  2025–26. Due date is “On Moodle”; no submission date is inferred here.
- [ ] Submit the complete ZIP via Moodle and confirm receipt/accessibility.

The sample and documentation are ready for review; no PDF, PPTX, final screenshots,
contribution record, rehearsal, ZIP or Moodle submission is claimed complete.
