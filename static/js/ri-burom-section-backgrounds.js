(function () {
    function applySectionBackgrounds() {
        var root = document.documentElement;
        var sectionMap = {
            'hero': '#rb-home-hero',
            'home_about': '#rb-home-about',
            'home_tours': '#rb-home-tours',
            'home_why': '#rb-home-why',
            'home_blog': '#rb-home-blog',
            'home_contact': '#rb-home-contact',
            'about_header': '#rb-about-header',
            'about_belief': '#about-belief',
            'about_pillars': '#about-pillars',
            'about_extra1': '#about-extra1',
            'about_extra2': '#about-extra2',
            'about_team': '#about-team',
            'about_logo': '#about-logo',
            'about_blog': '#about-blog',
            'footer': '.rb-footer'
        };

        Object.keys(sectionMap).forEach(function (key) {
            var el = document.querySelector(sectionMap[key]);
            var prefix = '--rb-' + key.replace(/_/g, '-') + '-';
            var image = root.style.getPropertyValue(prefix + 'bg-image').trim();
            if (!el || !image || image === 'none' || image === '""') return;

            var overlayColor = root.style.getPropertyValue(prefix + 'overlay-color').trim() || '#000000';
            var overlayOpacity = root.style.getPropertyValue(prefix + 'overlay-opacity').trim() || '0';
            var rgba = overlayColor;
            var match = overlayColor.match(/^#([0-9a-f]{6})$/i);
            if (match) {
                var hex = match[1];
                rgba = 'rgba(' + parseInt(hex.slice(0, 2), 16) + ',' + parseInt(hex.slice(2, 4), 16) + ',' + parseInt(hex.slice(4, 6), 16) + ',' + overlayOpacity + ')';
            }

            el.style.backgroundImage = 'linear-gradient(' + rgba + ',' + rgba + '),' + image;
            el.style.backgroundSize = 'cover';
            el.style.backgroundPosition = 'center';
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applySectionBackgrounds);
    } else {
        applySectionBackgrounds();
    }
})();
