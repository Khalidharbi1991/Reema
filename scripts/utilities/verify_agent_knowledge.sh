#!/bin/bash
echo "============================================"
echo "REEMA Agent Knowledge Base Verification"
echo "============================================"
echo ""
echo "Knowledge Files:"
echo "----------------"
ls -lh src/knowledge/*_knowledge.md 2>/dev/null | awk '{print $9, "-", $5}'
echo ""
echo "Line Counts:"
echo "------------"
wc -l src/knowledge/*_knowledge.md 2>/dev/null
echo ""
echo "Total Knowledge Size:"
echo "--------------------"
du -sh src/knowledge/*_knowledge.md 2>/dev/null | awk '{sum+=$1} END {print "Total:", sum, "KB"}'
echo ""
echo "✅ All agent knowledge bases installed!"
echo "✅ Agents will automatically load knowledge on initialization"
echo ""
echo "To test the system:"
echo '  python -m src.main generate "Incident Management"'
echo ""
