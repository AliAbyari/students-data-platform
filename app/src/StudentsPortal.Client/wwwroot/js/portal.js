window.portal = {
    storage: {
        get: key => {
            try { return localStorage.getItem(key) ?? sessionStorage.getItem(key); } catch { return null; }
        },
        set: (key, value, temporary) => {
            try {
                (temporary ? sessionStorage : localStorage).setItem(key, value);
                (temporary ? localStorage : sessionStorage).removeItem(key);
            } catch { }
        },
        isTemporary: key => {
            try { return localStorage.getItem(key) === null && sessionStorage.getItem(key) !== null; } catch { return false; }
        },
        remove: key => { try { localStorage.removeItem(key); sessionStorage.removeItem(key); } catch { } }
    },
    onShortcuts: dotnet => {
        window.portal.shortcutTarget = dotnet;
        if (window.portal.shortcutsBound) return;
        window.portal.shortcutsBound = true;
        document.addEventListener('keydown', e => {
            const target = window.portal.shortcutTarget;
            if (!target) return;
            const el = e.target;
            const typing = el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
            if (e.key === 'F1' || (e.key === '?' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey)) {
                e.preventDefault();
                target.invokeMethodAsync('OpenGuide').catch(() => { });
            } else if (e.key === 'Escape') {
                target.invokeMethodAsync('CloseGuide').catch(() => { });
            }
        });
    },
    applyDocument: (lang, dir, theme, title) => {
        const root = document.documentElement;
        root.lang = lang;
        root.dir = dir;
        root.dataset.theme = theme;
        if (title) document.title = title;
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = theme === 'light' ? '#e8eefc' : '#0b1220';
    },
    confirm: message => window.confirm(message),
    isOnline: () => navigator.onLine,
    onConnectivity: dotnet => {
        window.portal.connectivityTarget = dotnet;
        if (window.portal.connectivityBound) return;
        window.portal.connectivityBound = true;
        const notify = value => window.portal.connectivityTarget?.invokeMethodAsync('SetOnline', value).catch(() => { });
        window.addEventListener('online', () => notify(true));
        window.addEventListener('offline', () => notify(false));
    }
};
