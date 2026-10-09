from app.schemas.copilot import CopilotMessageIn
from app.api.v1.copilot import ask_copilot
from unittest.mock import patch, MagicMock

def test_ask_copilot_translation():
    mock_db = MagicMock()
    mock_access = MagicMock()
    mock_access.business_id = "biz1"
    mock_access.user.uid = "user1"
    
    # Mock repositories
    with patch("app.api.v1.copilot.records_repo") as mock_records, \
         patch("app.api.v1.copilot.conv_repo") as mock_conv, \
         patch("app.api.v1.copilot.compute_financial_metrics") as mock_metrics, \
         patch("app.api.v1.copilot.copilot_answer") as mock_answer, \
         patch("app.api.v1.copilot.get_translation_service") as mock_get_trans:
        
        mock_records.list_records.return_value = []
        mock_metrics.return_value.model_dump.return_value = {}
        
        mock_conv.create_conversation.return_value = {"id": "conv1"}
        
        mock_answer.return_value = {
            "answer": "This is the answer.",
            "category": "financial",
            "sources": [{"documentId": "doc1", "fileName": "f1.pdf", "page": 1, "sheetName": None}],
            "caveats": ["Caveat 1"],
            "recommended_actions": ["Action 1"],
            "timestamp": "2023-01-01T00:00:00Z"
        }
        
        mock_trans = MagicMock()
        # English to target
        mock_trans.translate_text.side_effect = lambda text, target_language, source_language=None: f"translated_{text}"
        mock_get_trans.return_value = mock_trans
        
        body = CopilotMessageIn(question="translated_question", language="hi", conversation_id=None)
        
        result = ask_copilot(body, mock_access, mock_db)
        
        # Verify translation was called on the question
        mock_trans.translate_text.assert_any_call(text="translated_question", target_language="en", source_language="hi")
        
        # Verify answer was translated
        assert result.answer == "translated_This is the answer."
        assert result.caveats == ["translated_Caveat 1"]
        assert result.recommended_actions == ["translated_Action 1"]
        assert result.sources[0].document_id == "doc1"
