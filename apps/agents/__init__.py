"""
Sistema de Sub-Agentes para generación de contenido.

Arquitectura:
    BaseAgent (ABC)
    ├── BriefEnricherAgent   — Expande idea cruda → brief estructurado
    ├── CopyAgent            — Genera captions, hooks, CTAs
    ├── HashtagAgent         — Genera hashtags optimizados
    ├── ImageAgent           — Genera prompts visuales → imagen
    ├── CarouselAgent        — Genera carrusel multi-slide
    └── VideoAgent           — Genera script → video/reel

Cada agente:
    1. Recibe un brief + brand context
    2. Construye un prompt con template + brand briefing
    3. Llama al provider correspondiente
    4. Valida y estructura el output
    5. Registra un AgentRun para trazabilidad
"""
