from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from observability import setup_logging

from app.adapters.inbound.rest_api import router as users_router
from app.config import settings
from app.domain.exceptions import (
    CurrentPasswordIncorrectException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="User Service",
    version="0.2.0",
    description="Handles user registration and authentication. "
    "Domain events are persisted via transactional outbox and "
    "published by a separate worker process.",
)


# P3-59: de fire handlere er servicens chokepunkt — hver domæneafvisning passerer her, så
# det er ét sted frem for hvert raise-sted.  Men de logger IKKE alle fire: admissionsreglen
# er "en afvisning fortjener en linje hvis og kun hvis statuskoden alene er tvetydig om
# årsagen", og efter P3-57 bærer hver request allerede en access-linje med metode, sti og
# statuskode.  Hvorfor de to fravalg er fravalg står på hver handler.


@app.exception_handler(UserAlreadyExistsException)
async def user_already_exists_handler(_request: Request, exc: UserAlreadyExistsException) -> JSONResponse:
    # LOGGER IKKE — bevidst fravalg, ikke en forglemmelse.  En 409 på /register eller
    # /me/username er en helt almindelig bruger der vælger et taget navn, og bodyen siger
    # allerede hvilket felt der kolliderede.  En linje her ville duplikere access-linjen.
    #
    # Den *tvetydighed* der findes i denne exception er om 409'en kom fra for-tjekket eller
    # fra en tabt race mod DB-constrainten — og det kan handleren ikke se.  Derfor logges
    # racen på sine to raise-steder i application/service.py i stedet.
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsException)
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsException) -> JSONResponse:
    # Mislykket login var indtil nu HELT uden spor, så credential-stuffing var usynligt.
    # 401'en er desuden med vilje tvetydig i kontrakten — "brugeren findes ikke" og
    # "forkert password" giver samme svar for ikke at afsløre hvilke konti der findes.
    # Den tvetydighed er rigtig udad, og præcis derfor skal den ikke også gælde indad.
    #
    # `username_or_email` er IKKE på linjen: brugere taster regelmæssigt deres password i
    # brugernavnsfeltet, så feltet ville lække adgangskoder i klartekst til loggen.
    # Kilde-IP'en, som er det der gør stuffing synligt, bærer access-linjen allerede.
    logger.warning("Mislykket login-forsøg på %s", request.url.path)
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(CurrentPasswordIncorrectException)
async def current_password_incorrect_handler(request: Request, exc: CurrentPasswordIncorrectException) -> JSONResponse:
    # 403, ikke 401. En 401 herfra ville få frontendens apiClient til at
    # rydde sessionen og redirecte til /login — altså logge brugeren ud
    # fordi de tastede deres nuværende password forkert.
    #
    # P3-59: 403'en har én teknisk årsag, men to *betydninger*, og det er dem den er
    # tvetydig om: en bruger der tastede forkert, eller en der holder et gyldigt token
    # uden at kende passwordet — signaturen på et stjålet token.  Statuskoden kan ikke
    # skelne dem; en ophobning på samme sti kan.
    logger.warning("Forkert nuværende password ved %s", request.url.path)
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(UserNotFoundException)
async def user_not_found_handler(request: Request, exc: UserNotFoundException) -> JSONResponse:
    # Samme exception, to tvetydigheder — derfor gates linjen på ruten:
    #
    # * fra `/me`-ruterne er den TVETYDIG og fortjener en linje: kaldet bar et gyldigt
    #   token, så brugeren er slettet under en levende session (eller der er udstedt et
    #   token for en bruger der ikke findes).  Begge er data-integritetssignaler.
    # * fra det interne `GET /{user_id}` er den ENTYDIG: en anden service spurgte om et id
    #   der ikke findes, og 404'en siger det hele.  Den gren er desuden hvordan
    #   account-service' `exists()` normalt svarer nej, så en linje der ville fyre ved helt
    #   almindelig brug — netop det admissionsreglen findes for at holde ude.
    if "/me" in request.url.path:
        logger.warning("Gyldigt token for en bruger der ikke findes: %s (sti=%s)", exc, request.url.path)
    return JSONResponse(status_code=404, content={"detail": str(exc)})


app.include_router(users_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "user-service"}
