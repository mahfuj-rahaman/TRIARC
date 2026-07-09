from orchestrator.security.ingress import wrap_untrusted


def test_wrap_untrusted_tags_content_with_source():
    wrapped = wrap_untrusted("rm -rf /", source="code-sandbox")

    assert wrapped.startswith('<untrusted-data source="code-sandbox">')
    assert wrapped.endswith("</untrusted-data>")
    assert "rm -rf /" in wrapped
