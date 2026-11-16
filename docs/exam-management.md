# EduTrack Exam Management

## Scope
- Organization admins can create exams with academic year, class/course, term and optional date.
- Each exam can contain multiple subjects with maximum and pass marks.
- Marks are entered per active student and subject. Draft marks can be updated.
- Results can be published only when every active student has a mark for every exam subject.
- Published results are read-only and visible only to matching student accounts in that organization.
- Existing assessment-history rows are preserved and remain visible separately.

## Database rollout
1. Back up the database.
2. Apply migration 008 if it has not already been applied.
3. Apply migrations/009_exam_management.sql.
4. Deploy the application code.
5. Test exam creation, marks entry, publishing, and student visibility with test accounts from two organizations.

No email, SMS, OTP, or credential-delivery integration is included in this phase.
