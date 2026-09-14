package com.ryoya0427.ankiwordcollector;

public final class LanguageDetector {
    private LanguageDetector() { }

    public static String detect(String text) {
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if ((c >= 0x3040 && c <= 0x30FF)) return "ja";
            if (c >= 0x4E00 && c <= 0x9FFF) return "zh-CN";
            if (c >= 0x0400 && c <= 0x052F) return "ru";
            if (c >= 0x0600 && c <= 0x06FF) return "ar";
            if (c >= 0x0900 && c <= 0x097F) return "hi";
        }
        return "en";
    }
}
