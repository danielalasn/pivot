// assets/theme.js

window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        switch_theme: function(pathname) {
            // 1. Detectar si el sistema del usuario está en Dark Mode
            let isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;

            // 2. Buscar la hoja de estilo de Dash Bootstrap Components
            let links = document.getElementsByTagName('link');
            let themeLink = null;

            for (let i = 0; i < links.length; i++) {
                if (links[i].href && (links[i].href.includes('cyborg') || links[i].href.includes('cosmo') || links[i].href.includes('bootstrap'))) {
                    themeLink = links[i];
                    break;
                }
            }

            // 3. Aplicar el cambio si es necesario
            if (themeLink) {
                if (isDarkMode) {
                    // El sistema es OSCURO -> Forzar CYBORG
                    if (!themeLink.href.includes('cyborg')) {
                        themeLink.href = themeLink.href.replace('cosmo', 'cyborg').replace('bootstrap', 'cyborg');
                    }
                } else {
                    // El sistema es CLARO -> Forzar COSMO
                    if (themeLink.href.includes('cyborg')) {
                        themeLink.href = themeLink.href.replace('cyborg', 'cosmo');
                    }
                }
            }
            return ""; // Retorno dummy
        }
    }
});