# Flask LMS (Phase 2)

This project is the first phase of a full Learning Management System (LMS) built with Flask and SQLAlchemy.

Implemented so far:
- Authentication system with role support (`admin`, `student`, `parent`)
- Pending approval workflow for new registrations
- Admin approval/rejection for pending users
- Main course and sub-course data model
- Main course access code entry in registration
- Automatic enrollment in main course from code (sub-courses unlock via parent access)
- Scalable Flask structure with Blueprints and app factory
- Learning delivery flow:
  - Sub-course pages with modules
  - Lessons (text, video, PDF)
  - Quiz attempts and submissions
  - Automatic grading and per-question results
  - Personal results history
- Messaging flow:
  - Inbox, sent messages, compose, and message detail pages
- Subscription/payment flow:
  - User plan browsing and subscribing
  - Subscription history and cancellation
  - Simulated successful payment transactions
- Admin content management:
  - Main courses and sub-courses
  - Modules, lessons, quizzes, and questions
  - Subscription plan management
  - Extra dashboard analytics counters
- Analytics:
  - Dedicated admin analytics page with role distribution, content volume, and quiz performance charts
- Admin teaching tools:
  - Admin teaching dashboard for instructional metrics
  - Content publishing workflow (publish/unpublish sub-courses, lessons, quizzes)
  - Manual grading override screen for quiz attempts

## Project structure

```text
lms/
  app/
    admin/
      forms.py
      routes.py
    auth/
      forms.py
      routes.py
    billing/
      routes.py
    learning/
      routes.py
    main/
      routes.py
    messaging/
      forms.py
      routes.py
    static/css/
      styles.css
    templates/
      admin/
      auth/
      main/
      base.html
    utils/
      decorators.py
    __init__.py
    extensions.py
    models.py
  config.py
  run.py
  requirements.txt
```

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables using `.env.example`.
4. Initialize database:
   ```bash
   flask --app run.py init-db
   ```
5. Create admin account:
   ```bash
   flask --app run.py create-admin
   ```
6. Create at least one main course (with access code):
   ```bash
   flask --app run.py seed-main-course
   ```
7. (Optional) Seed a plan and demo lesson/quiz content:
  ```bash
  flask --app run.py seed-plan
  flask --app run.py seed-demo-content
  ```
8. Run the app:
   ```bash
   flask --app run.py run
   ```

## Registration and approval flow

1. User registers and optionally enters a main course code.
2. Account is created with `is_approved = False`.
3. If code is valid, enrollment to that main course is created immediately.
4. User can sign in but sees pending approval page.
5. Admin approves user from the pending users page.
6. Approved user can access all sub-courses under enrolled main course.

## Notes

- Product model: admins are the teaching/assistant team and handle material publishing and grading.
- Enrollment is at main course level. Access to sub-courses is inherited.
- Payment integration is currently a simulated provider (`manual-demo`) for development.
- Next phase can add production payment gateways and richer analytics exports.
- In production, replace default secret key and use a production-ready database.
