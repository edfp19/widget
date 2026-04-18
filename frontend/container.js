(function (global) {
    'use strict';

    function isPromiseLike(value) {
        return !!value && typeof value.then === 'function';
    }

    function createPlaceholderFetch(label) {
        return function placeholderFetch(panel) {
            if (!panel.dataset.placeholderRendered) {
                panel.innerHTML = '<div class="sr-tab-placeholder">Loading ' + label + '...</div>';
                panel.dataset.placeholderRendered = 'true';
            }
        };
    }

    function normalizeTabOptions(options) {
        if (typeof options === 'boolean') {
            return {
                liveOnly: options,
                refreshOnLive: false
            };
        }

        return Object.assign(
            {
                liveOnly: false,
                refreshOnLive: false
            },
            options || {}
        );
    }

    class WidgetContainer {
        constructor(context, targetElement) {
            if (!targetElement || typeof targetElement.appendChild !== 'function') {
                throw new Error('[SR Widget] WidgetContainer requires a mount element.');
            }

            this.context = Object.assign(
                {
                    pageType: 'homepage',
                    matchId: null,
                    competitionId: null,
                    theme: 'light',
                    defaultTab: 'table',
                    apiBase: '',
                    pollIntervalMs: 5000
                },
                context || {}
            );

            this.root = document.createElement('div');
            this.root.className = 'sr-widget-root theme-' + this.context.theme;
            this.root.dataset.theme = this.context.theme;
            this.root.dataset.phase = 'PRE_MATCH';

            this.tabs = new Map();
            this.activeTabId = null;
            this._pollInterval = null;

            this.renderShell();
            targetElement.appendChild(this.root);
        }

        renderShell() {
            var showHeader = this.context.pageType === 'match' ? 'flex' : 'none';

            this.root.innerHTML = [
                '<header class="sr-match-header" style="display: ' + showHeader + ';">',
                '    <div class="sr-teams">Loading match...</div>',
                '    <div class="sr-score">- : -</div>',
                '    <div class="sr-minute">--\'</div>',
                '</header>',
                '<nav class="sr-tab-nav" role="tablist" aria-label="Widget tabs"></nav>',
                '<main class="sr-tab-viewport"></main>'
            ].join('');

            this.headerEl = this.root.querySelector('.sr-match-header');
            this.teamsEl = this.root.querySelector('.sr-teams');
            this.scoreEl = this.root.querySelector('.sr-score');
            this.minuteEl = this.root.querySelector('.sr-minute');
            this.navEl = this.root.querySelector('.sr-tab-nav');
            this.viewportEl = this.root.querySelector('.sr-tab-viewport');
        }

        updateHeader(state) {
            if (!state) {
                return;
            }

            var homeTeam = state.home_team || 'Home';
            var awayTeam = state.away_team || 'Away';
            var homeScore = state.home_score != null ? state.home_score : '-';
            var awayScore = state.away_score != null ? state.away_score : '-';
            var minuteText = state.phase === 'LIVE' && state.clock != null
                ? String(state.clock) + '\''
                : (state.phase || '--');

            this.context.homeScore = homeScore;
            this.context.awayScore = awayScore;
            this.context.homeTeamName = homeTeam;
            this.context.awayTeamName = awayTeam;

            this.teamsEl.textContent = homeTeam + ' vs ' + awayTeam;
            this.scoreEl.textContent = homeScore + ' : ' + awayScore;
            this.minuteEl.textContent = minuteText;
        }

        registerTab(id, label, fetchFn, options) {
            if (!id) {
                throw new Error('[SR Widget] registerTab requires a tab id.');
            }

            if (this.tabs.has(id)) {
                throw new Error('[SR Widget] Duplicate tab id "' + id + '".');
            }

            var resolvedOptions = normalizeTabOptions(options);
            var resolvedFetchFn = typeof fetchFn === 'function'
                ? fetchFn
                : createPlaceholderFetch(label || id);

            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'sr-tab-button';
            button.dataset.tabId = id;
            button.setAttribute('role', 'tab');
            button.setAttribute('aria-selected', 'false');
            button.textContent = label || id;

            if (resolvedOptions.liveOnly) {
                button.classList.add('sr-live-only');
                button.style.display = 'none';
            }

            var panel = document.createElement('section');
            panel.className = 'sr-tab-panel';
            panel.dataset.tabId = id;
            panel.setAttribute('role', 'tabpanel');
            panel.setAttribute('aria-hidden', 'true');
            panel.style.display = 'none';
            panel.innerHTML = '<div class="sr-tab-placeholder">Loading ' + (label || id) + '...</div>';

            if (resolvedOptions.liveOnly) {
                panel.classList.add('sr-live-only');
            }

            this.navEl.appendChild(button);
            this.viewportEl.appendChild(panel);

            var tab = {
                id: id,
                button: button,
                panel: panel,
                fetchFn: resolvedFetchFn,
                dataReady: false,
                fetchPromise: null,
                isLiveOnly: resolvedOptions.liveOnly,
                refreshOnLive: resolvedOptions.refreshOnLive
            };

            this.tabs.set(id, tab);
            button.addEventListener('click', () => this.activateTab(id));

            return tab;
        }

        refreshTab(id) {
            if (!this.tabs.has(id)) {
                return Promise.resolve(null);
            }

            var tab = this.tabs.get(id);
            if (tab.fetchPromise) {
                return tab.fetchPromise;
            }

            tab.fetchPromise = Promise.resolve()
                .then(() => tab.fetchFn(tab.panel, this.context, tab.id, this))
                .then((result) => {
                    if (!isPromiseLike(result)) {
                        tab.dataReady = true;
                        tab.panel.dataset.error = 'false';
                        return result;
                    }

                    return result.then((asyncResult) => {
                        tab.dataReady = true;
                        tab.panel.dataset.error = 'false';
                        return asyncResult;
                    });
                })
                .catch((error) => {
                    tab.panel.dataset.error = 'true';
                    console.warn('[SR Widget] Tab fetch failed for "' + tab.id + '":', error);
                    return null;
                })
                .finally(() => {
                    tab.fetchPromise = null;
                });

            return tab.fetchPromise;
        }

        initTabs() {
            if (!this.tabs.size) {
                return;
            }

            this.tabs.forEach((tab) => {
                this.refreshTab(tab.id);
            });

            var defaultId = this.tabs.has(this.context.defaultTab)
                ? this.context.defaultTab
                : this.tabs.keys().next().value;

            if (defaultId) {
                this.activateTab(defaultId);
            }
        }

        async ensureLiveSquadsView() {
            var squadsTab = this.tabs.get('squads');

            if (!squadsTab || typeof global.renderPitchView !== 'function') {
                return;
            }

            try {
                await this.refreshTab('squads');
                global.renderPitchView(squadsTab.panel, this.context);
            } catch (error) {
                console.warn('[SR Widget] Pitch view render failed:', error);
            }
        }

        activateTab(id) {
            if (!this.tabs.has(id)) {
                return false;
            }

            this.activeTabId = id;

            this.tabs.forEach((tab, tabId) => {
                var isActive = tabId === id;

                tab.button.classList.toggle('active', isActive);
                tab.button.setAttribute('aria-selected', isActive ? 'true' : 'false');
                tab.panel.style.display = isActive ? 'block' : 'none';
                tab.panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
            });

            var activeTab = this.tabs.get(id);
            if (this.root.dataset.phase === 'LIVE' && activeTab.refreshOnLive) {
                this.refreshTab(id);
            }

            if (id === 'squads' && this.root.dataset.phase === 'LIVE') {
                this.ensureLiveSquadsView();
            }

            return true;
        }

        revealLiveTabs() {
            var tabIds = Array.prototype.slice.call(arguments);

            tabIds.forEach((id) => {
                var tab = this.tabs.get(id);

                if (tab) {
                    tab.button.style.display = 'inline-block';
                }
            });
        }

        refreshActiveLiveTab() {
            if (!this.activeTabId || !this.tabs.has(this.activeTabId)) {
                return;
            }

            var activeTab = this.tabs.get(this.activeTabId);
            if (activeTab.refreshOnLive) {
                this.refreshTab(activeTab.id);
            }
        }

        startPolling() {
            if (this.context.pageType !== 'match') {
                return;
            }

            this.stopPolling();
            this._pollInterval = global.setInterval(
                () => this.pollMatchState(),
                this.context.pollIntervalMs || 5000
            );
        }

        stopPolling() {
            if (this._pollInterval) {
                global.clearInterval(this._pollInterval);
                this._pollInterval = null;
            }
        }

        async pollMatchState() {
            if (this.context.pageType !== 'match') {
                return null;
            }

            if (document.visibilityState !== 'visible') {
                return null;
            }

            if (!this.context.matchId) {
                return null;
            }

            var stateOverride = global.__srMockStateOverride;
            if (stateOverride && typeof stateOverride === 'object') {
                this.updateHeader(stateOverride);

                if (stateOverride.phase && stateOverride.phase !== this.root.dataset.phase) {
                    this.handlePhaseTransition(stateOverride.phase);
                }

                if (stateOverride.phase === 'LIVE') {
                    this.refreshActiveLiveTab();
                }

                return stateOverride;
            }

            try {
                var response = await global.fetch(
                    this.context.apiBase + '/match/' + this.context.matchId + '/state'
                );

                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }

                var payload = await response.json();
                var data = payload && Object.prototype.hasOwnProperty.call(payload, 'data')
                    ? payload.data
                    : payload;

                if (!data) {
                    return null;
                }

                this.updateHeader(data);

                if (data.phase && data.phase !== this.root.dataset.phase) {
                    this.handlePhaseTransition(data.phase);
                }

                if (data.phase === 'LIVE') {
                    this.refreshActiveLiveTab();
                }

                return data;
            } catch (error) {
                console.warn('[SR Widget] Poll failed:', error);
                return null;
            }
        }

        handlePhaseTransition(newPhase) {
            if (!newPhase) {
                return;
            }

            var previousPhase = this.root.dataset.phase || 'PRE_MATCH';
            this.context.phase = newPhase;
            this.root.dataset.phase = newPhase;

            if (newPhase === 'LIVE') {
                this.revealLiveTabs('xg-race', 'momentum');
                this.refreshActiveLiveTab();

                if (this.activeTabId === 'squads') {
                    this.ensureLiveSquadsView();
                }

                return;
            }

            if (newPhase === 'HALF_TIME') {
                this.refreshActiveLiveTab();
                return;
            }

            if (newPhase === 'FULL_TIME') {
                this.stopPolling();
                this.refreshActiveLiveTab();
                return;
            }

            if (newPhase === 'PRE_MATCH' && previousPhase !== 'PRE_MATCH') {
                this.tabs.forEach((tab) => {
                    if (tab.isLiveOnly || tab.id === 'xg-race' || tab.id === 'momentum') {
                        tab.button.style.display = 'none';
                    }
                });

                if (this.activeTabId) {
                    var activeTab = this.tabs.get(this.activeTabId);
                    if (activeTab && activeTab.button.style.display === 'none') {
                        var fallbackId = null;

                        this.tabs.forEach((tab, tabId) => {
                            if (!fallbackId && tab.button.style.display !== 'none') {
                                fallbackId = tabId;
                            }
                        });

                        if (fallbackId) {
                            this.activateTab(fallbackId);
                        }
                    }
                }
            }
        }
    }

    global.WidgetContainer = WidgetContainer;
}(window));
