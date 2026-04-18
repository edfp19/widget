(function () {
    'use strict';

    var ROOT_ID = 'sr-widget-root';
    var DEFAULTS = {
        pageType: 'homepage',
        matchId: null,
        competitionId: null,
        client: null,
        theme: 'light',
        defaultTab: 'table',
        apiBase: 'http://localhost:8080/api/v1',
        pollIntervalMs: 5000
    };

    function normalizeString(value, fallback) {
        if (typeof value !== 'string') {
            return fallback;
        }

        var normalized = value.trim();
        return normalized || fallback;
    }

    function normalizeNullableString(value) {
        if (typeof value !== 'string') {
            return null;
        }

        var normalized = value.trim();
        return normalized || null;
    }

    function normalizeInteger(value, fallback) {
        var parsed = parseInt(value, 10);

        if (!Number.isFinite(parsed) || parsed < 1000) {
            return fallback;
        }

        return parsed;
    }

    function deriveAssetBase(scriptNode) {
        var src = scriptNode && scriptNode.src ? scriptNode.src : '';

        if (!src) {
            return '/static';
        }

        return src.replace(/\/loader\.js(?:\?.*)?$/, '');
    }

    function loadScriptOnce(url) {
        var registry = window.__srAssetPromises || (window.__srAssetPromises = {});

        if (registry[url]) {
            return registry[url];
        }

        registry[url] = new Promise(function (resolve, reject) {
            var existing = document.querySelector('script[src="' + url + '"]');

            if (existing) {
                if (existing.dataset.srLoaded === 'true') {
                    resolve();
                    return;
                }

                existing.addEventListener('load', function onLoad() {
                    existing.dataset.srLoaded = 'true';
                    resolve();
                }, { once: true });
                existing.addEventListener('error', function onError() {
                    reject(new Error('[SR Widget] Failed to load dependency: ' + url));
                }, { once: true });
                return;
            }

            var script = document.createElement('script');
            script.src = url;
            script.async = false;
            script.dataset.srManaged = 'true';
            script.addEventListener('load', function () {
                script.dataset.srLoaded = 'true';
                resolve();
            }, { once: true });
            script.addEventListener('error', function () {
                reject(new Error('[SR Widget] Failed to load dependency: ' + url));
            }, { once: true });
            document.head.appendChild(script);
        });

        return registry[url];
    }

    function loadStylesheetOnce(url) {
        var existing = document.querySelector('link[rel="stylesheet"][href="' + url + '"]');

        if (existing) {
            return;
        }

        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        link.dataset.srManaged = 'true';
        document.head.appendChild(link);
    }

    async function ensureDependencies(scriptNode) {
        var assetBase = deriveAssetBase(scriptNode);
        loadStylesheetOnce(assetBase + '/widget.css');

        await Promise.all([
            loadScriptOnce(assetBase + '/renderers.js'),
            loadScriptOnce(assetBase + '/canvas_chart.js'),
            loadScriptOnce(assetBase + '/container.js')
        ]);
    }

    var ContextResolver = {
        init: function (scriptNode) {
            var node = scriptNode || document.currentScript || document.querySelector('script[src*="loader.js"]');

            if (!node) {
                throw new Error('[SR Widget] Unable to resolve loader script element.');
            }

            var dataset = node.dataset || {};
            var pageType = normalizeString(dataset.pageType, DEFAULTS.pageType);
            var matchId = normalizeNullableString(dataset.matchId);
            var competitionId = normalizeNullableString(dataset.competitionId);
            var legacyEntityId = normalizeNullableString(dataset.entityId);

            if (!matchId && pageType === 'match') {
                matchId = legacyEntityId;
            }

            if (!competitionId && pageType !== 'match') {
                competitionId = legacyEntityId;
            }

            var context = {
                pageType: pageType,
                matchId: matchId,
                competitionId: competitionId,
                client: normalizeNullableString(dataset.client),
                theme: normalizeString(dataset.theme, DEFAULTS.theme),
                defaultTab: normalizeString(dataset.defaultTab, DEFAULTS.defaultTab),
                apiBase: normalizeString(dataset.apiBase, DEFAULTS.apiBase),
                pollIntervalMs: normalizeInteger(dataset.pollIntervalMs, DEFAULTS.pollIntervalMs)
            };

            validateContext(context);
            console.info('[SR Widget] Resolved config:', context);

            return context;
        }
    };

    function validateContext(context) {
        if (context.pageType === 'match' && !context.matchId) {
            throw new Error('[SR Widget] Match context requires data-match-id.');
        }

        if (context.pageType !== 'match' && !context.competitionId && !context.matchId) {
            throw new Error('[SR Widget] Competition or homepage context requires data-competition-id.');
        }
    }

    function ensureRoot(scriptNode) {
        var existingRoot = document.getElementById(ROOT_ID);

        if (existingRoot) {
            return existingRoot;
        }

        var root = document.createElement('div');
        root.id = ROOT_ID;

        if (scriptNode && scriptNode.parentNode) {
            scriptNode.parentNode.insertBefore(root, scriptNode);
            return root;
        }

        if (!document.body) {
            throw new Error('[SR Widget] Unable to create widget root without a mount parent.');
        }

        document.body.appendChild(root);
        return root;
    }

    async function fetchEnvelope(url) {
        var response = await window.fetch(url);

        if (!response.ok) {
            throw new Error('Request failed for ' + url + ' with status ' + response.status + '.');
        }

        var payload = await response.json();
        return payload && Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload;
    }

    function registerCompetitionTabs(container, context) {
        container.registerTab('table', 'Table', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/competition/' + context.competitionId + '/table');
            window.SRRenderers.renderLeagueTable(panel, data, context);
        }, { refreshOnLive: true });

        container.registerTab('fixtures', 'Fixtures', async function (panel) {
            var payloads = await Promise.all([
                fetchEnvelope(context.apiBase + '/competition/' + context.competitionId + '/fixtures?status=scheduled&limit=5'),
                fetchEnvelope(context.apiBase + '/competition/' + context.competitionId + '/fixtures?status=played&limit=5')
            ]);

            window.SRRenderers.renderFixtures(panel, {
                scheduled: payloads[0],
                played: payloads[1]
            });
        }, { refreshOnLive: true });
    }

    function registerMatchTabs(container, context) {
        registerCompetitionTabs(container, context);

        container.registerTab('squads', 'Squads', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/match/' + context.matchId + '/squads');
            window.SRRenderers.renderSquads(panel, data, context, container);
        }, { refreshOnLive: true });

        container.registerTab('team-stats', 'Team Stats', async function (panel) {
            var teamId = context.homeTeamId || '1';
            var split = panel.__srTeamStatsSplit || 'season';
            var data = await fetchEnvelope(context.apiBase + '/team/' + teamId + '/stats?split=' + encodeURIComponent(split));
            window.SRRenderers.renderTeamStats(panel, data, {
                apiBase: context.apiBase,
                teamId: teamId,
                split: split
            });
        }, { refreshOnLive: true });

        container.registerTab('h2h', 'Head to Head', async function (panel) {
            var resultsUrl = context.apiBase + '/match/' + context.matchId + '/h2h?limit=5';
            var playersUrl = context.apiBase + '/match/' + context.matchId + '/h2h/players';
            var payloads = await Promise.all([fetchEnvelope(resultsUrl), fetchEnvelope(playersUrl)]);

            window.SRRenderers.renderH2H(panel, {
                results: payloads[0],
                selectorData: payloads[1],
                apiBase: context.apiBase,
                matchId: context.matchId
            });
        });

        container.registerTab('facts', 'Facts', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/match/' + context.matchId + '/facts?limit=10');
            window.SRRenderers.renderMatchFacts(panel, data, {
                phase: context.phase
            });
        }, { refreshOnLive: true });

        container.registerTab('xg-race', 'xG Race', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/match/' + context.matchId + '/xg-race');
            window.renderXgChart(panel, data);
        }, { liveOnly: true, refreshOnLive: true });
    }

    async function prepareContext(context) {
        if (context.pageType !== 'match') {
            context.competitionId = context.competitionId || context.matchId || '39';
            return {
                initialState: null,
                context: context
            };
        }

        var initialState = await fetchEnvelope(context.apiBase + '/match/' + context.matchId + '/state');
        context.competitionId = initialState.competition_id || context.competitionId || '39';
        context.phase = initialState.phase || 'PRE_MATCH';
        context.homeTeamName = initialState.home_team || null;
        context.awayTeamName = initialState.away_team || null;
        context.homeScore = initialState.home_score;
        context.awayScore = initialState.away_score;

        try {
            var squads = await fetchEnvelope(context.apiBase + '/match/' + context.matchId + '/squads');
            context.homeTeamId = squads && squads.home ? squads.home.team_id : null;
            context.awayTeamId = squads && squads.away ? squads.away.team_id : null;
        } catch (error) {
            console.warn('[SR Widget] Unable to resolve team ids from squads payload:', error);
        }

        return {
            initialState: initialState,
            context: context
        };
    }

    async function boot() {
        var scriptNode = document.currentScript || document.querySelector('script[src*="loader.js"]');
        await ensureDependencies(scriptNode);

        var context = ContextResolver.init(scriptNode);
        var mountNode = ensureRoot(scriptNode);
        var prepared = await prepareContext(context);

        if (typeof window.WidgetContainer !== 'function') {
            throw new Error('[SR Widget] WidgetContainer dependency failed to load.');
        }

        if (!window.SRRenderers || typeof window.renderXgChart !== 'function') {
            throw new Error('[SR Widget] Renderer dependencies failed to load.');
        }

        var instance = new window.WidgetContainer(prepared.context, mountNode);

        if (prepared.context.pageType === 'match') {
            registerMatchTabs(instance, prepared.context);
        } else {
            registerCompetitionTabs(instance, prepared.context);
        }

        instance.initTabs();

        if (prepared.initialState) {
            instance.updateHeader(prepared.initialState);
            instance.handlePhaseTransition(prepared.initialState.phase || 'PRE_MATCH');
            instance.startPolling();
        }

        window.__srContainer = instance;
        window.__srWidgetContext = prepared.context;
        window.SRWidget = {
            ContextResolver: ContextResolver,
            context: prepared.context,
            mountNode: mountNode,
            instance: instance
        };
    }

    boot().catch(function (error) {
        console.error('[SR Widget] Boot failed:', error);
    });
}());
