import pytest
import asyncio
import json
from src.state import JobState
from src.routers.jobs import _live_event_generator, _format_event, _format_result_event

def test_format_event():
    assert _format_event({'type': 'log', 'data': {'text': 'log1'}}) == {'data': '{"text": "log1"}'}
    assert _format_event({'type': 'node', 'data': {'id': '1'}}) == {'event': 'node', 'data': '{"id": "1"}'}
    assert _format_event({'type': 'other'}) == {}

def test_format_result_event():
    job = JobState()
    job.status = 'completed'
    job.original_skill = 'skill'
    job.result = 'result'
    job.mcts_nodes = []
    res = _format_result_event(job)
    assert res['event'] == 'result'
    assert json.loads(res['data']) == {
        'status': 'completed',
        'original': 'skill',
        'optimized': 'result',
        'nodes': []
    }

@pytest.mark.asyncio
async def test_live_event_generator_happy_path():
    job = JobState()
    job.original_skill = "skill"
    job.result = "result"
    job.mcts_nodes = []
    job.events_queue = asyncio.Queue()

    # Pre-populate queue
    job.events_queue.put_nowait({'type': 'log', 'data': {'text': 'log1'}})
    job.events_queue.put_nowait({'type': 'node', 'data': {'id': '1'}})
    job.status = 'completed'

    generator = _live_event_generator(job)

    events = []
    async for event in generator:
        events.append(event)

    assert len(events) == 4
    assert json.loads(events[0]['data']) == {'text': 'log1'}
    assert events[1]['event'] == 'node'
    assert events[2]['event'] == 'result'
    assert events[3]['event'] == 'end'

@pytest.mark.asyncio
async def test_live_event_generator_timeout_and_error():
    job = JobState()
    job.events_queue = asyncio.Queue()
    job.status = 'error'

    generator = _live_event_generator(job)

    events = []
    async for event in generator:
        events.append(event)

    assert len(events) == 1
    assert events[0]['event'] == 'end'
    assert events[0]['data'] == 'error'
