"""Current-research-group daily goals, daily reports, and mentor feedback endpoints."""

from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_current_team_admin_membership, require_current_team_membership
from app.models import DailyGoal, DailyReport, HourlySummary, MentorFeedback, ScreenSession, TeamMember, User
from app.schemas import (
    DailyGoalOut,
    DailyGoalUpsert,
    DailyReportDetailOut,
    DailyReportOut,
    DailyReportUpsert,
    HourlySummaryOut,
    MentorFeedbackCreate,
    MentorFeedbackOut,
    SessionOut,
    TeamMemberOut,
)
from app.services.audit import record_audit_log

router = APIRouter(tags=["learning"])

AUTH_RESPONSE = {401: {"description": "Missing, invalid, or expired bearer token."}}
CURRENT_TEAM_RESPONSES = {
    **AUTH_RESPONSE,
    404: {"description": "Current research group was not found or caller is not an active member."},
}
USER_ID_PATH = Path(..., description="Student user ID in the current research group.")


def _date_bounds(value: date) -> tuple[datetime, datetime]:
    return datetime.combine(value, time.min), datetime.combine(value, time.max)


def _load_goal(db: Session, team_id: int, user_id: int, goal_date: date) -> DailyGoal | None:
    return db.scalar(
        select(DailyGoal).where(
            DailyGoal.team_id == team_id,
            DailyGoal.user_id == user_id,
            DailyGoal.goal_date == goal_date,
        )
    )


def _load_report(db: Session, team_id: int, user_id: int, report_date: date) -> DailyReport | None:
    return db.scalar(
        select(DailyReport).where(
            DailyReport.team_id == team_id,
            DailyReport.user_id == user_id,
            DailyReport.report_date == report_date,
        )
    )


def _load_student_membership(db: Session, team_id: int, user_id: int) -> TeamMember:
    membership = db.scalar(
        select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return membership


def _member_out(db: Session, membership: TeamMember) -> TeamMemberOut:
    member_user = db.get(User, membership.user_id)
    if member_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    active_session = db.scalar(
        select(ScreenSession)
        .where(
            ScreenSession.team_id == membership.team_id,
            ScreenSession.user_id == membership.user_id,
            ScreenSession.status == "active",
        )
        .order_by(ScreenSession.started_at.desc())
    )
    latest_summary = db.scalar(
        select(HourlySummary.summary_text)
        .where(HourlySummary.team_id == membership.team_id, HourlySummary.user_id == membership.user_id)
        .order_by(desc(HourlySummary.hour_start))
    )
    return TeamMemberOut(
        user_id=member_user.id,
        email=member_user.email,
        name=member_user.name,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        active_session=SessionOut.model_validate(active_session) if active_session else None,
        latest_summary=latest_summary,
    )


def _report_detail(db: Session, team_id: int, user_id: int, report_date: date) -> DailyReportDetailOut:
    membership = _load_student_membership(db, team_id, user_id)
    start_at, end_at = _date_bounds(report_date)
    summaries = db.scalars(
        select(HourlySummary)
        .where(
            HourlySummary.team_id == team_id,
            HourlySummary.user_id == user_id,
            HourlySummary.hour_start >= start_at,
            HourlySummary.hour_start <= end_at,
        )
        .order_by(HourlySummary.hour_start.asc())
    ).all()
    feedback = db.scalars(
        select(MentorFeedback)
        .where(
            MentorFeedback.team_id == team_id,
            MentorFeedback.user_id == user_id,
            MentorFeedback.report_date == report_date,
        )
        .order_by(MentorFeedback.created_at.desc())
    ).all()
    return DailyReportDetailOut(
        student=_member_out(db, membership),
        goal=DailyGoalOut.model_validate(goal) if (goal := _load_goal(db, team_id, user_id, report_date)) else None,
        report=DailyReportOut.model_validate(report) if (report := _load_report(db, team_id, user_id, report_date)) else None,
        hourly_summaries=[HourlySummaryOut.model_validate(summary) for summary in summaries],
        feedback=[MentorFeedbackOut.model_validate(item) for item in feedback],
    )


@router.get(
    "/daily-goals/my",
    response_model=DailyGoalOut | None,
    summary="Get my daily goal",
    responses=CURRENT_TEAM_RESPONSES,
)
def my_daily_goal(
    goal_date: date = Query(description="Goal date."),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyGoalOut | None:
    membership = require_current_team_membership(db, user)
    goal = _load_goal(db, membership.team_id, user.id, goal_date)
    return DailyGoalOut.model_validate(goal) if goal else None


@router.put(
    "/daily-goals/my",
    response_model=DailyGoalOut,
    summary="Create or update my daily goal",
    responses=CURRENT_TEAM_RESPONSES,
)
def upsert_my_daily_goal(
    payload: DailyGoalUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyGoalOut:
    membership = require_current_team_membership(db, user)
    goal = _load_goal(db, membership.team_id, user.id, payload.goal_date)
    if goal is None:
        goal = DailyGoal(team_id=membership.team_id, user_id=user.id, goal_date=payload.goal_date, main_goal=payload.main_goal)
        db.add(goal)
    goal.main_goal = payload.main_goal
    goal.planned_tasks = payload.planned_tasks
    goal.expected_challenges = payload.expected_challenges
    goal.needs_mentor_help = payload.needs_mentor_help
    db.flush()
    record_audit_log(db, membership.team_id, user.id, "daily_goal.submitted", "daily_goal", goal.id)
    db.commit()
    db.refresh(goal)
    return DailyGoalOut.model_validate(goal)


@router.get(
    "/daily-reports/my",
    response_model=list[DailyReportOut],
    summary="List my daily reports",
    responses=CURRENT_TEAM_RESPONSES,
)
def my_daily_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DailyReportOut]:
    membership = require_current_team_membership(db, user)
    reports = db.scalars(
        select(DailyReport)
        .where(DailyReport.team_id == membership.team_id, DailyReport.user_id == user.id)
        .order_by(DailyReport.report_date.desc())
    ).all()
    return [DailyReportOut.model_validate(report) for report in reports]


@router.get(
    "/daily-reports/my/detail",
    response_model=DailyReportDetailOut,
    summary="Get my daily report detail",
    responses=CURRENT_TEAM_RESPONSES,
)
def my_daily_report_detail(
    report_date: date = Query(description="Report date."),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyReportDetailOut:
    membership = require_current_team_membership(db, user)
    return _report_detail(db, membership.team_id, user.id, report_date)


@router.put(
    "/daily-reports/my",
    response_model=DailyReportOut,
    summary="Create or update my daily report",
    responses=CURRENT_TEAM_RESPONSES,
)
def upsert_my_daily_report(
    payload: DailyReportUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyReportOut:
    membership = require_current_team_membership(db, user)
    report = _load_report(db, membership.team_id, user.id, payload.report_date)
    if report is None:
        report = DailyReport(
            team_id=membership.team_id,
            user_id=user.id,
            report_date=payload.report_date,
            completed_work=payload.completed_work,
        )
        db.add(report)
    report.completed_work = payload.completed_work
    report.problems = payload.problems
    report.next_plan = payload.next_plan
    report.needs_mentor_help = payload.needs_mentor_help
    report.notes = payload.notes
    db.flush()
    record_audit_log(db, membership.team_id, user.id, "daily_report.submitted", "daily_report", report.id)
    db.commit()
    db.refresh(report)
    return DailyReportOut.model_validate(report)


@router.get(
    "/mentor/students/{user_id}/daily-reports",
    response_model=list[DailyReportOut],
    summary="List one student's daily reports",
    responses={**CURRENT_TEAM_RESPONSES, 403: {"description": "Caller is not a current research group mentor."}},
)
def student_daily_reports(
    user_id: Annotated[int, USER_ID_PATH],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DailyReportOut]:
    membership = require_current_team_admin_membership(db, user)
    _load_student_membership(db, membership.team_id, user_id)
    reports = db.scalars(
        select(DailyReport)
        .where(DailyReport.team_id == membership.team_id, DailyReport.user_id == user_id)
        .order_by(DailyReport.report_date.desc())
    ).all()
    return [DailyReportOut.model_validate(report) for report in reports]


@router.get(
    "/mentor/students/{user_id}/daily-report",
    response_model=DailyReportDetailOut,
    summary="Get one student's daily report detail",
    responses={**CURRENT_TEAM_RESPONSES, 403: {"description": "Caller is not a current research group mentor."}},
)
def student_daily_report_detail(
    user_id: Annotated[int, USER_ID_PATH],
    report_date: date = Query(description="Report date."),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyReportDetailOut:
    membership = require_current_team_admin_membership(db, user)
    return _report_detail(db, membership.team_id, user_id, report_date)


@router.post(
    "/mentor/students/{user_id}/feedback",
    response_model=MentorFeedbackOut,
    summary="Create mentor feedback for a student's daily report",
    responses={**CURRENT_TEAM_RESPONSES, 403: {"description": "Caller is not a current research group mentor."}},
)
def create_student_feedback(
    user_id: Annotated[int, USER_ID_PATH],
    payload: MentorFeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MentorFeedbackOut:
    membership = require_current_team_admin_membership(db, user)
    _load_student_membership(db, membership.team_id, user_id)
    feedback = MentorFeedback(
        team_id=membership.team_id,
        user_id=user_id,
        mentor_user_id=user.id,
        report_date=payload.report_date,
        content=payload.content,
        score=payload.score,
        status_mark=payload.status_mark,
        next_step=payload.next_step,
        needs_meeting=payload.needs_meeting,
    )
    db.add(feedback)
    db.flush()
    record_audit_log(db, membership.team_id, user.id, "mentor_feedback.created", "mentor_feedback", feedback.id)
    db.commit()
    db.refresh(feedback)
    return MentorFeedbackOut.model_validate(feedback)
