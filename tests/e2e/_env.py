"""Hemmeligheder til e2e-tests, læst fra miljøet — aldrig hardkodet.

Tidligere hardkodede de tre e2e-filer `dev-secret-key-change-in-production`,
og det "virkede" udelukkende fordi docker-compose.yml hardkodede den samme
literal. Det gjorde CI's e2e-job misvisende: jobbet satte selv
JWT_SECRET=test-secret, men testene ignorerede den og signerede med
dev-strengen alligevel — og fandt alligevel en stak der brugte dev-strengen.
Med interpolation i compose (P2-26) er der ikke længere en fælles literal at
falde tilbage på, så værdien skal komme fra ét sted: miljøet.

Slået op ved kaldstid frem for ved import, så en manglende variabel ikke
bliver en collection-fejl der maskerer conftest'ens skip-når-services-er-nede.
"""

from __future__ import annotations

import os

JWT_ALGORITHM = "HS256"


def jwt_secret() -> str:
    """Den delte HS256-nøgle stakken kører med.

    Fejler med en handlingsbar besked frem for at signere med en tom streng:
    et token signeret med "" ville give 401 i hver service, og fejlen ville
    se ud som et auth-problem i produktionskoden i stedet for en
    manglende variabel i test-miljøet.
    """
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET er ikke sat i miljøet. e2e-tests skal signere med "
            "samme nøgle som stakken kører med.\n"
            "  lokalt: brug `make test-e2e` (loader .env), eller "
            "`set -a; . ./.env; set +a` først\n"
            "  CI:     jobbet skal sætte JWT_SECRET som env — samme værdi "
            "som compose interpolerer"
        )
    return secret
