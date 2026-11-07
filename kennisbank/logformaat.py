import json
import logging
from datetime import UTC, datetime

_STANDAARD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Eén JSON-object per regel, met eventuele extra velden uit `extra={...}`."""

    def format(self, record):
        regel = {
            "tijd": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "niveau": record.levelname,
            "logger": record.name,
            "bericht": record.getMessage(),
        }
        for sleutel, waarde in vars(record).items():
            if sleutel == "request" and hasattr(waarde, "path"):
                # Django hangt het request-object aan 4xx/5xx-logregels. Alleen methode en pad loggen,
                # nooit de querystring: daar kunnen zoektermen (en dus namen of zaaknummers) in staan.
                regel["methode"] = getattr(waarde, "method", "")
                regel["pad"] = waarde.path
                continue
            if sleutel not in _STANDAARD and not sleutel.startswith("_"):
                try:
                    json.dumps(waarde)
                    regel[sleutel] = waarde
                except TypeError:
                    regel[sleutel] = str(waarde)
        if record.exc_info:
            regel["fout"] = self.formatException(record.exc_info)
        return json.dumps(regel, ensure_ascii=False)
