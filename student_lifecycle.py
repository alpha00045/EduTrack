from datetime import date
from flask import abort, flash, redirect, render_template, request, session, url_for


def register_student_lifecycle_routes(app, organization_required, get_db_connection):
    """Register tenant-scoped promotion, transfer, graduation and withdrawal workflows."""

    @app.route("/organization/students/<path:roll>/lifecycle", methods=["GET", "POST"])
    @organization_required
    def organization_student_lifecycle(roll):
        organization_id = session["organization_id"]
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT s.id,s.roll_number,s.name,o.organization_type,
                          p.admission_standard,p.section,p.course_name,p.semester,
                          p.academic_year,COALESCE(p.student_status,'Active')
                   FROM organization_students s
                   JOIN organizations o ON o.id=s.organization_id
                   LEFT JOIN organization_student_profiles p
                     ON p.organization_id=s.organization_id AND p.student_id=s.id
                   WHERE s.organization_id=%s AND s.roll_number=%s
                   FOR UPDATE OF s""",
                (organization_id, roll),
            )
            student = cur.fetchone()
            if not student:
                abort(404)

            student_id, student_roll, name, organization_type = student[:4]
            current = {
                "standard": student[4] or "",
                "section": student[5] or "",
                "course_name": student[6] or "",
                "semester": student[7] or "",
                "academic_year": student[8] or "",
                "status": student[9],
            }

            if request.method == "POST":
                action = (request.form.get("action") or "").strip()
                effective_raw = (request.form.get("effective_date") or "").strip()
                try:
                    effective_date = date.fromisoformat(effective_raw) if effective_raw else date.today()
                except ValueError:
                    flash("Enter a valid effective date.", "danger")
                    return redirect(url_for("organization_student_lifecycle", roll=roll))

                if current["status"] != "Active":
                    flash("Only active students can be promoted or have a new transfer/exit recorded.", "warning")
                    return redirect(url_for("organization_student_details", roll=roll))

                if action == "promote":
                    academic_year = (request.form.get("academic_year") or "").strip()[:20]
                    standard = (request.form.get("standard") or "").strip()[:40] or None
                    section = (request.form.get("section") or "").strip()[:30] or None
                    course_name = (request.form.get("course_name") or "").strip()[:120] or None
                    semester = (request.form.get("semester") or "").strip()[:20] or None
                    if not academic_year:
                        flash("Enter the new academic year.", "danger")
                        return redirect(url_for("organization_student_lifecycle", roll=roll))
                    if organization_type == "School" and not standard:
                        flash("Enter the next class or standard.", "danger")
                        return redirect(url_for("organization_student_lifecycle", roll=roll))
                    if organization_type == "Institute" and (not course_name or not semester):
                        flash("Enter the course and semester for the new enrolment.", "danger")
                        return redirect(url_for("organization_student_lifecycle", roll=roll))
                    new_placement = (academic_year, standard, section, course_name, semester)
                    old_placement = (current["academic_year"], current["standard"] or None,
                                     current["section"] or None, current["course_name"] or None,
                                     current["semester"] or None)
                    if new_placement == old_placement:
                        flash("The new enrolment is identical to the current placement.", "warning")
                        return redirect(url_for("organization_student_lifecycle", roll=roll))

                    cur.execute(
                        """UPDATE organization_student_enrolments
                           SET end_date=%s,status='Completed'
                           WHERE organization_id=%s AND student_id=%s AND status='Active'""",
                        (effective_date, organization_id, student_id),
                    )
                    cur.execute(
                        """INSERT INTO organization_student_enrolments
                           (organization_id,student_id,academic_year,organization_type,
                            standard,section,course_name,semester,start_date,status)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Active')""",
                        (organization_id, student_id, academic_year, organization_type,
                         standard if organization_type == "School" else None,
                         section if organization_type == "School" else None,
                         course_name if organization_type == "Institute" else None,
                         semester if organization_type == "Institute" else None,
                         effective_date),
                    )
                    cur.execute(
                        """UPDATE organization_student_profiles
                           SET academic_year=%s,admission_standard=%s,section=%s,
                               course_name=%s,semester=%s,student_status='Active'
                           WHERE organization_id=%s AND student_id=%s""",
                        (academic_year, standard if organization_type == "School" else None,
                         section if organization_type == "School" else None,
                         course_name if organization_type == "Institute" else None,
                         semester if organization_type == "Institute" else None,
                         organization_id, student_id),
                    )
                    conn.commit()
                    flash("Student promoted / new enrolment recorded. Previous enrolment history has been preserved.", "success")
                    return redirect(url_for("organization_student_details", roll=roll))

                exit_actions = {
                    "transfer": ("Transferred", "Transferred", "Disabled", "Student transfer recorded."),
                    "graduate": ("Graduated", "Completed", "Disabled", "Student graduation recorded."),
                    "withdraw": ("Inactive", "Withdrawn", "Disabled", "Student withdrawal recorded."),
                }
                if action not in exit_actions:
                    flash("Choose a valid student lifecycle action.", "danger")
                    return redirect(url_for("organization_student_lifecycle", roll=roll))
                profile_status, enrolment_status, account_status, message = exit_actions[action]
                cur.execute(
                    """UPDATE organization_student_enrolments
                       SET end_date=%s,status=%s
                       WHERE organization_id=%s AND student_id=%s AND status='Active'""",
                    (effective_date, enrolment_status, organization_id, student_id),
                )
                cur.execute(
                    """UPDATE organization_student_profiles SET student_status=%s
                       WHERE organization_id=%s AND student_id=%s""",
                    (profile_status, organization_id, student_id),
                )
                cur.execute(
                    """UPDATE organization_student_accounts SET account_status=%s,updated_at=CURRENT_TIMESTAMP
                       WHERE organization_id=%s AND student_id=%s""",
                    (account_status, organization_id, student_id),
                )
                conn.commit()
                flash(message + " Student login has been disabled.", "success")
                return redirect(url_for("organization_student_details", roll=roll))

            cur.execute(
                """SELECT academic_year,standard,section,course_name,semester,
                          start_date,end_date,status
                   FROM organization_student_enrolments
                   WHERE organization_id=%s AND student_id=%s
                   ORDER BY created_at DESC,id DESC""",
                (organization_id, student_id),
            )
            history = cur.fetchall()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

        return render_template(
            "organizations/student_lifecycle.html",
            student={"roll": student_roll, "name": name, "organization_type": organization_type,
                     **current},
            history=history,
        )
