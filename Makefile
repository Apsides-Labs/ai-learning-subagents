.PHONY: install test setup weekly article measure validate mark-published list-calendar

install:
	uv sync

test:
	uv run pytest

setup:
	uv run python main.py --mode setup

weekly:
	uv run python main.py --mode weekly

article:
	uv run python main.py --mode article

measure:
	uv run python main.py --mode measure

validate:
	uv run python main.py --mode validate

# Mark an article published. ID is the calendar entry id (matches blog slug).
# URL defaults to https://www.draftandarc.com/blog/<ID> if not set.
# Usage:
#   make mark-published ID=anki-review-queue-burnout
#   make mark-published ID=anki-review-queue-burnout URL=https://www.draftandarc.com/blog/anki-review-queue-burnout
mark-published:
	@test -n "$(ID)" || (echo "ERROR: ID is required. Usage: make mark-published ID=<slug> [DATE=YYYY-MM-DD]"; exit 1)
	uv run python main.py --mark-published $(ID) \
		--url $(or $(URL),https://www.draftandarc.com/blog/$(ID)) \
		$(if $(DATE),--date $(DATE),)

# Show all calendar entries and their status
list-calendar:
	@uv run python -c "\
import asyncio; \
from services.calendar_service import load_calendar; \
async def m(): \
    entries = await load_calendar(); \
    [print(f'{e.status:25} {e.id:50} {e.live_url or \"-\"}') for e in entries] \
; asyncio.run(m())"
