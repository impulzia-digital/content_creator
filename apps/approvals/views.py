"""Views del backoffice – Aprobaciones."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.approvals.models import ApprovalRequest
from apps.content.models import ContentBrief


@login_required
def approval_list(request):
    """Aprobaciones pendientes para la marca activa."""
    brand = request.brand
    if not brand:
        return redirect("brands:brand_list")

    pending = ApprovalRequest.objects.filter(
        variant__brief__brand=brand,
        decision=ApprovalRequest.Decision.PENDING,
    ).select_related("variant__brief")

    context = {"approvals": pending}

    if request.htmx:
        return render(request, "approvals/partials/approval_table.html", context)
    return render(request, "approvals/approval_list.html", context)


@login_required
def approval_decide(request, approval_id):
    """Aprobar, rechazar o solicitar cambios."""
    approval = get_object_or_404(
        ApprovalRequest, pk=approval_id, variant__brief__brand=request.brand
    )

    if request.method == "POST":
        decision = request.POST.get("decision", "")
        notes = request.POST.get("notes", "").strip()

        if decision not in dict(ApprovalRequest.Decision.choices):
            if request.htmx:
                return HttpResponse("Decisión inválida", status=400)
            return redirect("approvals:approval_list")

        approval.decision = decision
        approval.decided_by = request.user
        approval.decided_at = timezone.now()
        approval.notes = notes
        approval.save()

        # Si se aprueba, actualizar el brief
        brief = approval.variant.brief
        if decision == ApprovalRequest.Decision.APPROVED:
            brief.status = ContentBrief.Status.APPROVED
            brief.save(update_fields=["status"])

        if request.htmx:
            label = approval.get_decision_display()
            color = {"approved": "green", "rejected": "red"}.get(decision, "yellow")
            return HttpResponse(
                f'<span class="text-{color}-600 font-bold">{label}</span>'
            )
        return redirect("approvals:approval_list")

    return render(request, "approvals/approval_decide.html", {"approval": approval})
