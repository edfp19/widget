(function () {
    'use strict';

    var ROOT_ID = 'sr-widget-root';
    var DEFAULTS = {
        pageType: 'homepage',
        entityId: null,
        theme: 'light',
        defaultTab: 'table',
        apiBase: 'http://localhost:8080/api/v1'
    };

    var ContextResolver = {
        init: function (scriptNode) {
            var node = scriptNode || document.currentScript || document.querySelector('script[src*="loader.js"]');

            if (!node) {
                throw new Error('[SR Widget] Unable to resolve loader script element.');
            }

            var dataset = node.dataset || {};
            var context = {
                pageType: normalizeString(dataset.pageType, DEFAULTS.pageType),
                entityId: normalizeNullableString(dataset.entityId),
                theme: normalizeString(dataset.theme, DEFAULTS.theme),
                defaultTab: normalizeString(dataset.defaultTab, DEFAULTS.defaultTab),
                apiBase: normalizeString(dataset.apiBase, DEFAULTS.apiBase)
            };

            validateContext(context);
            console.info('[SR Widget] Resolved config:', context);

            return context;
        }
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

    function validateContext(context) {
        if (context.pageType === 'match' && !context.entityId) {
            throw new Error('[SR Widget] Match context requires data-entity-id attribute.');
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
            window.SRRenderers.renderLeagueTable(panel, data);
        });

        container.registerTab('fixtures', 'Fixtures', async function (panel) {
            var data = await fetchEnvelope(
                context.apiBase + '/competition/' + context.competitionId + '/fixtures?limit=5'
            );
            window.SRRenderers.renderFixtures(panel, data);
        });
    }

    function registerMatchTabs(container, context) {
        registerCompetitionTabs(container, context);

        container.registerTab('squads', 'Squads', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/match/' + context.entityId + '/squads');
            window.SRRenderers.renderSquads(panel, data, context, container);
        });

        container.registerTab('team-stats', 'Team Stats', async function (panel) {
            var teamId = context.primaryTeamId || '1';
            var data = await fetchEnvelope(context.apiBase + '/team/' + teamId + '/stats?split=season');
            window.SRRenderers.renderTeamStats(panel, data);
        });

        container.registerTab('h2h', 'Head to Head', async function (panel) {
            var resultsUrl = context.apiBase + '/match/' + context.entityId + '/h2h?limit=5';
            var playersUrl = context.apiBase + '/match/' + context.entityId + '/h2h/players';
            var payloads = await Promise.all([fetchEnvelope(resultsUrl), fetchEnvelope(playersUrl)]);

            window.SRRenderers.renderH2H(panel, {
                results: payloads[0],
                selectorData: payloads[1],
                apiBase: context.apiBase,
                matchId: context.entityId
            });
        });

        container.registerTab('facts', 'Facts', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/match/' + context.entityId + '/facts?limit=8');
            window.SRRenderers.renderMatchFacts(panel, data);
        });

        container.registerTab('xg-race', 'xG Race', async function (panel) {
            var data = await fetchEnvelope(context.apiBase + '/match/' + context.entityId + '/xg-race');
            window.renderXgChart(panel, data);
        }, true);
    }

    async function prepareContext(context) {
        if (context.pageType !== 'match') {
            context.competitionId = context.entityId || '39';
            return {
                initialState: null,
                context: context
            };
        }

        var initialState = await fetchEnvelope(context.apiBase + '/match/' + context.entityId + '/state');
        context.competitionId = initialState.competition_id || '39';
        context.primaryTeamId = '1';
        context.phase = initialState.phase || 'PRE_MATCH';

        return {
            initialState: initialState,
            context: context
        };
    }

    async function boot() {
        var scriptNode = document.currentScript || document.querySelector('script[src*="loader.js"]');
        var context = ContextResolver.init(scriptNode);
        var mountNode = ensureRoot(scriptNode);
        var instance;
        var prepared;

        if (typeof window.WidgetContainer !== 'function') {
            console.warn('[SR Widget] window.WidgetContainer is not available yet; container boot skipped.');
            return;
        }

        if (!window.SRRenderers || typeof window.renderXgChart !== 'function') {
            console.warn('[SR Widget] Renderer dependencies are not available yet; container boot skipped.');
            return;
        }

        prepared = await prepareContext(context);
        instance = new window.WidgetContainer(prepared.context, mountNode);

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
