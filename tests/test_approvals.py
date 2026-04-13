"""Tests para apps.approvals — ApprovalRequest."""

import pytest
from django.utils import timezone

from apps.approvals.models import ApprovalRequest


@pytest.mark.django_db
class TestApprovalRequest:
    def test_create_approval(self, variant, user):
        approval = ApprovalRequest.objects.create(
            variant=variant,
            requested_by=user,
        )
        assert approval.pk is not None
        assert approval.decision == ApprovalRequest.Decision.PENDING
        assert approval.decided_by is None
        assert approval.decided_at is None

    def test_approval_str(self, variant, user):
        approval = ApprovalRequest.objects.create(
            variant=variant, requested_by=user
        )
        s = str(approval)
        assert "Pendiente" in s

    def test_approve_variant(self, variant, user, admin_user):
        approval = ApprovalRequest.objects.create(
            variant=variant, requested_by=user
        )
        approval.decision = ApprovalRequest.Decision.APPROVED
        approval.decided_by = admin_user
        approval.decided_at = timezone.now()
        approval.save()

        approval.refresh_from_db()
        assert approval.decision == "approved"
        assert approval.decided_by == admin_user
        assert approval.decided_at is not None

    def test_reject_with_notes(self, variant, user, admin_user):
        approval = ApprovalRequest.objects.create(
            variant=variant, requested_by=user
        )
        approval.decision = ApprovalRequest.Decision.REJECTED
        approval.decided_by = admin_user
        approval.notes = "El caption no refleja el tono de marca"
        approval.decided_at = timezone.now()
        approval.save()

        approval.refresh_from_db()
        assert approval.decision == "rejected"
        assert "tono de marca" in approval.notes

    def test_changes_requested(self, variant, user, admin_user):
        approval = ApprovalRequest.objects.create(
            variant=variant, requested_by=user
        )
        approval.decision = ApprovalRequest.Decision.CHANGES_REQUESTED
        approval.notes = "Cambiar el hook, agregar más emojis"
        approval.decided_by = admin_user
        approval.decided_at = timezone.now()
        approval.save()

        assert approval.decision == "changes_requested"

    def test_decision_choices(self):
        decisions = [c[0] for c in ApprovalRequest.Decision.choices]
        assert "pending" in decisions
        assert "approved" in decisions
        assert "rejected" in decisions
        assert "changes_requested" in decisions

    def test_multiple_approval_rounds(self, variant, user, admin_user):
        # Primera ronda: rechazado
        a1 = ApprovalRequest.objects.create(variant=variant, requested_by=user)
        a1.decision = ApprovalRequest.Decision.REJECTED
        a1.decided_by = admin_user
        a1.decided_at = timezone.now()
        a1.save()

        # Segunda ronda: aprobado
        a2 = ApprovalRequest.objects.create(variant=variant, requested_by=user)
        a2.decision = ApprovalRequest.Decision.APPROVED
        a2.decided_by = admin_user
        a2.decided_at = timezone.now()
        a2.save()

        assert variant.approval_requests.count() == 2

    def test_ordering(self, variant, user):
        a1 = ApprovalRequest.objects.create(variant=variant, requested_by=user)
        a2 = ApprovalRequest.objects.create(variant=variant, requested_by=user)
        approvals = list(ApprovalRequest.objects.all())
        assert approvals[0] == a2  # Más reciente primero
