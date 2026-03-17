import { createContext, useState, useContext, createElement } from 'react';

const STORAGE_KEY = 'acds_settings';

function loadFromStorage() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch { return {}; }
}

function saved(key, fallback) {
    const s = loadFromStorage();
    return key in s ? s[key] : fallback;
}

function persist(key, value) {
    const s = loadFromStorage();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...s, [key]: value }));
}

export const SettingsContext = createContext({
    autoScroll: true, hideNoise: false, verboseTs: false, demoMode: false,
    setAutoScroll: () => { }, setHideNoise: () => { }, setVerboseTs: () => { }, setDemoMode: () => { },
});

export function SettingsProvider({ children }) {
    const [autoScroll, _setAutoScroll] = useState(() => saved('autoScroll', true));
    const [hideNoise, _setHideNoise] = useState(() => saved('hideNoise', false));
    const [verboseTs, _setVerboseTs] = useState(() => saved('verboseTs', false));
    const [demoMode, _setDemoMode] = useState(() => saved('demoMode', false));

    const setAutoScroll = v => { _setAutoScroll(v); persist('autoScroll', v); };
    const setHideNoise = v => { _setHideNoise(v); persist('hideNoise', v); };
    const setVerboseTs = v => { _setVerboseTs(v); persist('verboseTs', v); };
    const setDemoMode = v => { _setDemoMode(v); persist('demoMode', v); };

    // createElement avoids JSX in a .js file (Rollup rejects JSX in non-.jsx files)
    return createElement(
        SettingsContext.Provider,
        { value: { autoScroll, hideNoise, verboseTs, demoMode, setAutoScroll, setHideNoise, setVerboseTs, setDemoMode } },
        children
    );
}

export const useSettings = () => useContext(SettingsContext);
