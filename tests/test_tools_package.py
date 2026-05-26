def _is_tool(x) -> bool:
    """LangChain @tool produces a StructuredTool which is not callable() but exposes invoke/ainvoke."""
    return hasattr(x, "invoke") or hasattr(x, "ainvoke")


def test_research_agent_imports_still_work():
    from tools import jina_reader, tavily_search_tool, list_codebase_files, read_codebase_file
    assert _is_tool(jina_reader)
    assert tavily_search_tool is not None
    assert _is_tool(list_codebase_files)
    assert _is_tool(read_codebase_file)


def test_seo_agent_imports_still_work():
    """seo_agent.py still imports these until Task 14; they must be real tools, not stubs."""
    from tools import people_also_ask, google_trends
    assert _is_tool(people_also_ask)
    assert _is_tool(google_trends)
