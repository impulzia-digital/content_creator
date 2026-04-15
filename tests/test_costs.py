import pytest

from apps.content.models import AgentRun


pytestmark = pytest.mark.django_db


def _success_run(*, brief, agent_type, cost, variant=None):
    return AgentRun.objects.create(
        brief=brief,
        variant=variant,
        agent_type=agent_type,
        status=AgentRun.RunStatus.SUCCESS,
        cost_usd=cost,
    )


class TestBriefCostProperties:
    def test_total_cost_uses_latest_successful_generation(self, brief, variant):
        variant.is_selected = True
        variant.save(update_fields=["is_selected"])

        _success_run(
            brief=brief,
            agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            cost=0.0010,
        )
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.IMAGE,
            cost=0.0400,
        )
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.COPY,
            cost=0.0005,
        )

        _success_run(
            brief=brief,
            agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            cost=0.0020,
        )
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.IMAGE,
            cost=0.0500,
        )
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.COPY,
            cost=0.0007,
        )

        assert float(brief.latest_generation_cost_usd) == pytest.approx(0.0527, abs=1e-4)
        assert float(brief.total_cost_usd) == pytest.approx(0.0527, abs=1e-4)

    def test_total_cost_prefers_selected_variant_when_backfilled(self, brief, variant):
        variant.is_selected = True
        variant.generation_cost_usd = 0.1234
        variant.save(update_fields=["is_selected", "generation_cost_usd"])

        _success_run(
            brief=brief,
            agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            cost=0.0500,
        )

        assert float(brief.total_cost_usd) == pytest.approx(0.1234, abs=1e-4)


class TestVariantDisplayCost:
    def test_selected_variant_falls_back_to_brief_total(self, brief, variant):
        variant.is_selected = True
        variant.save(update_fields=["is_selected"])

        _success_run(
            brief=brief,
            agent_type=AgentRun.AgentType.BRIEF_ENRICHER,
            cost=0.0010,
        )
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.IMAGE,
            cost=0.0400,
        )

        assert float(variant.display_generation_cost_usd) == pytest.approx(0.0410, abs=1e-4)

    def test_unselected_variant_falls_back_to_own_runs(self, brief, variant):
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.IMAGE,
            cost=0.0400,
        )
        _success_run(
            brief=brief,
            variant=variant,
            agent_type=AgentRun.AgentType.COPY,
            cost=0.0008,
        )

        assert float(variant.display_generation_cost_usd) == pytest.approx(0.0408, abs=1e-4)