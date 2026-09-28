"""Simple translations for the citizen-facing pages (English, Hindi, Gujarati).

NOTE: Hindi and Gujarati translations were drafted quickly for the hackathon and
should be checked by a native speaker before real use. In production we would use
Bhashini (Government of India's language platform) for more languages.

Usage:
    from i18n import t
    t("title", "gu")
    t("under_guarantee", "hi", dlp_end="2027-01-01", contractor="X", deadline="...", defect_id="D-0001")
"""

LANGUAGES = {"en": "English", "hi": "हिन्दी", "gu": "ગુજરાતી"}

LABELS = {
    "en": {
        "title": "Report a problem",
        "language": "Language",
        "reporter": "I am a",
        "citizen": "Citizen",
        "engineer": "Engineer",
        "select_work": "Which public work?",
        "select_placeholder": "Search by name, ward or ID",
        "problem_type": "What is the problem?",
        "pothole": "Pothole",
        "crack": "Crack",
        "waterlogging": "Waterlogging",
        "light": "Light not working",
        "other": "Other",
        "describe": "Describe the problem (optional)",
        "describe_required": "Please describe the problem.",
        "photo": "Add a photo (optional)",
        "your_name": "Your name (optional)",
        "submit": "Submit",
        "no_work": "Please select a work.",
        "thank_you": "Thank you! Your report is recorded.",
        "under_guarantee": ("Under guarantee until {dlp_end}. Contractor {contractor} must repair "
                            "FREE by {deadline}. Notice ID: {defect_id}"),
        "city_repair": ("Guarantee ended on {dlp_end}. Added to city maintenance queue. "
                        "ID: {defect_id}"),
        # --- Public Board ---
        "board_title": 'Public work information',
        "not_found": 'This work was not found. Please choose from the list.',
        "ward": 'Ward',
        "asset_type": 'Type',
        "built_by": 'Built by',
        "cost": 'Cost',
        "completed_on": 'Completed on',
        "guarantee_until": 'UNDER GUARANTEE until {date}',
        "guarantee_ended": 'GUARANTEE ENDED on {date}',
        "guarantee_note": 'If it breaks now, the contractor must repair it FREE.',
        "ended_note": 'The city maintains this work now.',
        "rating": 'Contractor rating',
        "open_defects": 'Open problems',
        "last_repair": 'Last repair',
        "none": 'None',
        "report_button": 'Report a problem',
        "timeline": 'History of this work',
        "Road": 'Road',
        "Bridge": 'Bridge',
        "Drain": 'Drain',
        "Building": 'Building',
        "Streetlight": 'Streetlight',
        # --- UI extras ---
        "hero_sub": 'Tell us what is broken. We instantly check who must fix it.',
        "result_contractor_h": 'Contractor must repair it FREE',
        "result_city_h": 'City will repair it',
        "photo_too_big": 'Photo must be under 5 MB.',
        "board_sub": 'See who built it, what it cost, and how long it is guaranteed.',
    },
    "hi": {
        "title": "समस्या दर्ज करें",
        "language": "भाषा",
        "reporter": "मैं हूँ",
        "citizen": "नागरिक",
        "engineer": "इंजीनियर",
        "select_work": "कौन सा सार्वजनिक काम?",
        "select_placeholder": "नाम, वार्ड या आईडी से खोजें",
        "problem_type": "समस्या क्या है?",
        "pothole": "गड्ढा",
        "crack": "दरार",
        "waterlogging": "जलभराव",
        "light": "लाइट बंद है",
        "other": "अन्य",
        "describe": "समस्या बताएं (वैकल्पिक)",
        "describe_required": "कृपया समस्या बताएं।",
        "photo": "फोटो जोड़ें (वैकल्पिक)",
        "your_name": "आपका नाम (वैकल्पिक)",
        "submit": "जमा करें",
        "no_work": "कृपया एक काम चुनें।",
        "thank_you": "धन्यवाद! आपकी शिकायत दर्ज हो गई है।",
        "under_guarantee": ("{dlp_end} तक गारंटी में है। ठेकेदार {contractor} को {deadline} तक "
                            "मुफ्त मरम्मत करनी होगी। नोटिस आईडी: {defect_id}"),
        "city_repair": ("गारंटी {dlp_end} को खत्म हो गई। नगर निगम की मरम्मत सूची में जोड़ा गया। "
                        "आईडी: {defect_id}"),
        # --- Public Board ---
        "board_title": 'सार्वजनिक काम की जानकारी',
        "not_found": 'यह काम नहीं मिला। कृपया सूची से चुनें।',
        "ward": 'वार्ड',
        "asset_type": 'प्रकार',
        "built_by": 'बनाने वाला',
        "cost": 'लागत',
        "completed_on": 'पूरा हुआ',
        "guarantee_until": '{date} तक गारंटी में',
        "guarantee_ended": 'गारंटी {date} को खत्म',
        "guarantee_note": 'अभी टूटे तो ठेकेदार को मुफ्त मरम्मत करनी होगी।',
        "ended_note": 'अब नगर निगम इसकी देखभाल करता है।',
        "rating": 'ठेकेदार रेटिंग',
        "open_defects": 'खुली समस्याएं',
        "last_repair": 'आखिरी मरम्मत',
        "none": 'कोई नहीं',
        "report_button": 'समस्या दर्ज करें',
        "timeline": 'इस काम का इतिहास',
        "Road": 'सड़क',
        "Bridge": 'पुल',
        "Drain": 'नाली',
        "Building": 'इमारत',
        "Streetlight": 'स्ट्रीट लाइट',
        # --- UI extras ---
        "hero_sub": 'बताइए क्या टूटा है। हम तुरंत बताएंगे कि इसे कौन ठीक करेगा।',
        "result_contractor_h": 'ठेकेदार मुफ्त में ठीक करेगा',
        "result_city_h": 'नगर निगम ठीक करेगा',
        "photo_too_big": 'फोटो 5 MB से छोटी होनी चाहिए।',
        "board_sub": 'देखें किसने बनाया, कितनी लागत, और गारंटी कब तक है।',
    },
    "gu": {
        "title": "સમસ્યા નોંધાવો",
        "language": "ભાષા",
        "reporter": "હું છું",
        "citizen": "નાગરિક",
        "engineer": "ઇજનેર",
        "select_work": "કયું જાહેર કામ?",
        "select_placeholder": "નામ, વોર્ડ અથવા ID થી શોધો",
        "problem_type": "સમસ્યા શું છે?",
        "pothole": "ખાડો",
        "crack": "તિરાડ",
        "waterlogging": "પાણી ભરાવું",
        "light": "લાઇટ બંધ છે",
        "other": "અન્ય",
        "describe": "સમસ્યા લખો (વૈકલ્પિક)",
        "describe_required": "કૃપા કરીને સમસ્યા લખો.",
        "photo": "ફોટો ઉમેરો (વૈકલ્પિક)",
        "your_name": "તમારું નામ (વૈકલ્પિક)",
        "submit": "મોકલો",
        "no_work": "કૃપા કરીને એક કામ પસંદ કરો.",
        "thank_you": "આભાર! તમારી ફરિયાદ નોંધાઈ ગઈ છે.",
        "under_guarantee": ("{dlp_end} સુધી ગેરંટીમાં છે. કોન્ટ્રાક્ટર {contractor} એ {deadline} "
                            "સુધીમાં મફત સમારકામ કરવું પડશે. નોટિસ ID: {defect_id}"),
        "city_repair": ("ગેરંટી {dlp_end} ના રોજ પૂરી થઈ. મહાનગરપાલિકાની સમારકામ યાદીમાં ઉમેર્યું. "
                        "ID: {defect_id}"),
        # --- Public Board ---
        "board_title": 'જાહેર કામની માહિતી',
        "not_found": 'આ કામ મળ્યું નહીં. કૃપા કરીને યાદીમાંથી પસંદ કરો.',
        "ward": 'વોર્ડ',
        "asset_type": 'પ્રકાર',
        "built_by": 'બનાવનાર',
        "cost": 'ખર્ચ',
        "completed_on": 'પૂર્ણ થયું',
        "guarantee_until": '{date} સુધી ગેરંટીમાં',
        "guarantee_ended": 'ગેરંટી {date} ના રોજ પૂરી',
        "guarantee_note": 'હવે તૂટે તો કોન્ટ્રાક્ટરે મફત સમારકામ કરવું પડશે.',
        "ended_note": 'હવે મહાનગરપાલિકા આ કામની જાળવણી કરે છે.',
        "rating": 'કોન્ટ્રાક્ટર રેટિંગ',
        "open_defects": 'ખુલ્લી સમસ્યાઓ',
        "last_repair": 'છેલ્લું સમારકામ',
        "none": 'કોઈ નહીં',
        "report_button": 'સમસ્યા નોંધાવો',
        "timeline": 'આ કામનો ઇતિહાસ',
        "Road": 'રસ્તો',
        "Bridge": 'પુલ',
        "Drain": 'ગટર',
        "Building": 'ઇમારત',
        "Streetlight": 'સ્ટ્રીટ લાઇટ',
        # --- UI extras ---
        "hero_sub": 'શું તૂટ્યું છે તે કહો. તેને કોણ ઠીક કરશે તે અમે તરત જણાવીશું.',
        "result_contractor_h": 'કોન્ટ્રાક્ટર મફતમાં સમારકામ કરશે',
        "result_city_h": 'મહાનગરપાલિકા સમારકામ કરશે',
        "photo_too_big": 'ફોટો 5 MB થી નાનો હોવો જોઈએ.',
        "board_sub": 'કોણે બનાવ્યું, કેટલો ખર્ચ, અને ગેરંટી ક્યાં સુધી છે તે જુઓ.',
    },
}


def t(key, lang="en", **values):
    """Return the label for `key` in `lang`, falling back to English, then to the key itself.
    Extra keyword arguments fill {placeholders} in the text."""
    text = LABELS.get(lang, {}).get(key) or LABELS["en"].get(key) or key
    return text.format(**values) if values else text
