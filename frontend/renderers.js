(function (global) {
    'use strict';

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatDate(value) {
        try {
            return new Intl.DateTimeFormat('en-GB', {
                day: '2-digit',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            }).format(new Date(value));
        } catch (error) {
            return value;
        }
    }

    function getFormBadgeClass(result) {
        if (result === 'W') {
            return 'is-win';
        }

        if (result === 'D') {
            return 'is-draw';
        }

        return 'is-loss';
    }

    function normalizeSquadGroup(position) {
        if (position === 'GK') {
            return 'GK';
        }

        if (/^(RB|LB|CB|RWB|LWB|DEF)$/i.test(position)) {
            return 'DEF';
        }

        if (/^(DM|CM|AM|MID)$/i.test(position)) {
            return 'MID';
        }

        return 'FWD';
    }

    function isInPlayPhase(phase) {
        return phase === 'LIVE' || phase === 'HALF_TIME' || phase === 'FULL_TIME';
    }

    function renderInlineStatus(message, testId, modifierClass) {
        var className = modifierClass ? ' sr-tab-placeholder--' + modifierClass : '';
        return '<div class="sr-tab-placeholder' + className + '" data-testid="' + testId + '">' +
            escapeHtml(message) +
            '</div>';
    }

    function getVisibleLiveEvents(team, context) {
        var events = Array.isArray(team.live_events) ? team.live_events : [];

        if (!context || !isInPlayPhase(context.phase)) {
            return [];
        }

        if (context.phase === 'FULL_TIME') {
            return events;
        }

        var clock = Number(context.clock);
        if (!Number.isFinite(clock)) {
            return events;
        }

        return events.filter(function (event) {
            return typeof event.minute !== 'number' || event.minute <= clock;
        });
    }

    function renderLeagueTable(panel, rows, context) {
        panel.__srTableRows = rows;
        panel.__srTableContext = context;

        var selectedView = panel.__srTableView || 'overall';
        var highlightedTeams = {};

        if (context && context.homeTeamName) {
            highlightedTeams[context.homeTeamName] = 'is-home';
        }

        if (context && context.awayTeamName) {
            highlightedTeams[context.awayTeamName] = 'is-away';
        }

        var liveSummary = '';
        if (context && context.phase === 'LIVE') {
            liveSummary = [
                '<div class="sr-live-summary">',
                '<strong>Live table mode</strong>',
                '<span>' + escapeHtml(context.homeTeamName || 'Home') + ' ' +
                    escapeHtml(String(context.homeScore != null ? context.homeScore : '-')) +
                    ' - ' +
                    escapeHtml(String(context.awayScore != null ? context.awayScore : '-')) +
                    ' ' + escapeHtml(context.awayTeamName || 'Away') + '</span>',
                '</div>'
            ].join('');
        }

        function getStats(row) {
            if (selectedView === 'home' && row.home) {
                return row.home;
            }

            if (selectedView === 'away' && row.away) {
                return row.away;
            }

            return row;
        }

        function renderMovement(row) {
            if (typeof row.previous_position !== 'number') {
                return '<span class="sr-movement is-flat">=</span>';
            }

            var delta = row.previous_position - row.position;
            if (delta > 0) {
                return '<span class="sr-movement is-up" title="Up ' + delta + ' places">+</span>';
            }

            if (delta < 0) {
                return '<span class="sr-movement is-down" title="Down ' + Math.abs(delta) + ' places">-</span>';
            }

            return '<span class="sr-movement is-flat" title="No change">=</span>';
        }

        panel.innerHTML = [
            '<div class="sr-panel-heading">Premier League Table</div>',
            '<div class="sr-toolbar" role="group" aria-label="League table view">',
            '<span class="sr-control-label">View</span>',
            '<div class="sr-view-controls">',
            '<button type="button" aria-pressed="' + (selectedView === 'overall' ? 'true' : 'false') + '" class="sr-view-toggle' + (selectedView === 'overall' ? ' active' : '') + '" data-view="overall">Overall</button>',
            '<button type="button" aria-pressed="' + (selectedView === 'home' ? 'true' : 'false') + '" class="sr-view-toggle' + (selectedView === 'home' ? ' active' : '') + '" data-view="home">Home</button>',
            '<button type="button" aria-pressed="' + (selectedView === 'away' ? 'true' : 'false') + '" class="sr-view-toggle' + (selectedView === 'away' ? ' active' : '') + '" data-view="away">Away</button>',
            '</div>',
            '</div>',
            liveSummary,
            '<div class="sr-table-wrap">',
            '<table class="sr-data-table">',
            '<thead><tr><th>Pos</th><th>Move</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th><th>Form</th></tr></thead>',
            '<tbody>',
            rows.map(function (row) {
                var rowClass = highlightedTeams[row.team_name] ? ' class="' + highlightedTeams[row.team_name] + '"' : '';
                var stats = getStats(row);

                return [
                    '<tr' + rowClass + '>',
                    '<td>' + row.position + '</td>',
                    '<td>' + renderMovement(row) + '</td>',
                    '<td>' + escapeHtml(row.team_name) + '</td>',
                    '<td>' + stats.played + '</td>',
                    '<td>' + stats.won + '</td>',
                    '<td>' + stats.drawn + '</td>',
                    '<td>' + stats.lost + '</td>',
                    '<td>' + stats.gd + '</td>',
                    '<td><strong>' + stats.points + '</strong></td>',
                    '<td><div class="sr-form-row">',
                    row.form.map(function (result) {
                        return '<span class="sr-form-badge ' + getFormBadgeClass(result) + '">' + result + '</span>';
                    }).join(''),
                    '</div></td>',
                    '</tr>'
                ].join('');
            }).join(''),
            '</tbody></table></div>'
        ].join('');

        if (!panel.__srTableClickBound) {
            panel.addEventListener('click', function (event) {
                var button = event.target.closest('.sr-view-toggle');

                if (!button || !panel.contains(button)) {
                    return;
                }

                var nextView = button.dataset.view || 'overall';
                if (panel.__srTableView === nextView) {
                    return;
                }

                panel.__srTableView = nextView;
                renderLeagueTable(panel, panel.__srTableRows || rows, panel.__srTableContext || context);
            });
            panel.__srTableClickBound = true;
        }
    }

    function renderFixturesSection(title, fixtures) {
        if (!fixtures.length) {
            return [
                '<section class="sr-fixture-section">',
                '<div class="sr-subheading">' + escapeHtml(title) + '</div>',
                '<div class="sr-tab-placeholder">No items available.</div>',
                '</section>'
            ].join('');
        }

        return [
            '<section class="sr-fixture-section">',
            '<div class="sr-subheading">' + escapeHtml(title) + '</div>',
            '<div class="sr-fixtures-list">',
            fixtures.map(function (fixture) {
                var score = fixture.home_score == null || fixture.away_score == null
                    ? 'vs'
                    : fixture.home_score + ' - ' + fixture.away_score;

                return [
                    '<div class="sr-fixture-row">',
                    '<div class="sr-fixture-meta">' + escapeHtml(formatDate(fixture.date)) + '</div>',
                    '<div class="sr-fixture-main">',
                    '<span>' + escapeHtml(fixture.home_team) + '</span>',
                    '<strong>' + escapeHtml(score) + '</strong>',
                    '<span>' + escapeHtml(fixture.away_team) + '</span>',
                    '</div>',
                    '<div class="sr-fixture-status">' + escapeHtml(fixture.status.toUpperCase()) + '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>',
            '</section>'
        ].join('');
    }

    function renderFixtures(panel, payload) {
        var scheduled = Array.isArray(payload.scheduled) ? payload.scheduled.slice() : [];
        var played = Array.isArray(payload.played) ? payload.played.slice() : [];

        scheduled.sort(function (a, b) {
            return new Date(a.date) - new Date(b.date);
        });
        played.sort(function (a, b) {
            return new Date(b.date) - new Date(a.date);
        });

        panel.innerHTML = [
            '<div class="sr-panel-heading">Fixtures and Results</div>',
            '<div class="sr-fixture-columns">',
            renderFixturesSection('Next 5 Fixtures', scheduled),
            renderFixturesSection('Last 5 Results', played),
            '</div>'
        ].join('');
    }

    function renderStatsBody(data, statKeys) {
        return [
            '<div class="sr-stats-list">',
            statKeys.map(function (entry) {
                var key = entry[0];
                var label = entry[1];
                var homeValue = Number(data.home[key]);
                var awayValue = Number(data.away[key]);
                var maxValue = Math.max(homeValue, awayValue, 1);
                var homeWidth = (homeValue / maxValue) * 100;
                var awayWidth = (awayValue / maxValue) * 100;

                return [
                    '<div class="sr-stat-row">',
                    '<div class="sr-stat-label">' + escapeHtml(label) + '</div>',
                    '<div class="sr-stat-values">',
                    '<div class="sr-stat-team">',
                    '<span>' + escapeHtml(String(homeValue)) + '</span>',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-home" style="width: ' + homeWidth + '%;"></div></div>',
                    '</div>',
                    '<div class="sr-stat-team is-away">',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-away" style="width: ' + awayWidth + '%;"></div></div>',
                    '<span>' + escapeHtml(String(awayValue)) + '</span>',
                    '</div>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function renderTeamStats(panel, data, options) {
        var selectedSplit = (options && options.split) || panel.__srTeamStatsSplit || 'season';
        var inPlay = !!(options && isInPlayPhase(options.phase));

        if (!inPlay && selectedSplit === 'live') {
            selectedSplit = 'season';
        }

        var statKeys = selectedSplit === 'live'
            ? [
                ['possession_pct', 'Possession'],
                ['shots', 'Shots'],
                ['shots_on_target', 'Shots on Target'],
                ['corners', 'Corners'],
                ['fouls', 'Fouls'],
                ['yellow_cards', 'Yellow Cards'],
                ['red_cards', 'Red Cards']
            ]
            : [
                ['goals_for_avg', 'Goals For'],
                ['goals_against_avg', 'Goals Against'],
                ['xg_for_avg', 'xG For'],
                ['xg_against_avg', 'xG Against'],
                ['possession_pct', 'Possession'],
                ['shots_per_game', 'Shots'],
                ['shots_on_target_per_game', 'Shots on Target']
            ];

        panel.__srTeamStatsSplit = selectedSplit;

        panel.innerHTML = [
            '<div class="sr-panel-heading">Team Comparison</div>',
            '<div class="sr-toolbar">',
            '<label class="sr-control-label" for="sr-team-stats-split">Split</label>',
            '<select id="sr-team-stats-split" class="sr-inline-select" data-testid="widget-team-stats-split">',
            '<option value="season">Season</option>',
            '<option value="last_5">Last 5</option>',
            '<option value="last_10">Last 10</option>',
            '<option value="home">Home</option>',
            '<option value="away">Away</option>',
            inPlay ? '<option value="live">Live Match</option>' : '',
            '</select>',
            '</div>',
            renderStatsBody(data, statKeys)
        ].join('');

        var select = panel.querySelector('#sr-team-stats-split');
        select.value = selectedSplit;

        if (options && options.endpoint) {
            select.addEventListener('change', async function () {
                panel.__srTeamStatsSplit = select.value;
                panel.querySelector('.sr-stats-list').innerHTML = renderInlineStatus(
                    'Updating stats...',
                    'widget-team-stats-loading'
                );

                try {
                    var response = await global.fetch(options.endpoint + '?split=' + encodeURIComponent(select.value));
                    var payload = await response.json();
                    renderTeamStats(panel, payload.data, Object.assign({}, options, {
                        split: select.value,
                        phase: options.phase
                    }));
                } catch (error) {
                    panel.querySelector('.sr-stats-list').innerHTML = renderInlineStatus(
                        'Unable to update stats.',
                        'widget-team-stats-error',
                        'error'
                    );
                }
            });
        }
    }

    function summarizeH2H(results, options) {
        var fallbackMatch = results[0] || {};
        var homeTeamName = (options && options.homeTeamName) || fallbackMatch.home_team || 'Home';
        var awayTeamName = (options && options.awayTeamName) || fallbackMatch.away_team || 'Away';
        var summary = {
            homeTeamName: homeTeamName,
            awayTeamName: awayTeamName,
            meetings: results.length,
            home: {
                wins: 0,
                draws: 0,
                losses: 0,
                goalsFor: 0,
                goalsAgainst: 0,
                xgFor: 0,
                cleanSheets: 0
            },
            away: {
                wins: 0,
                draws: 0,
                losses: 0,
                goalsFor: 0,
                goalsAgainst: 0,
                xgFor: 0,
                cleanSheets: 0
            }
        };

        results.forEach(function (match) {
            var isHomePerspective = match.home_team === homeTeamName;
            var homeGoals = isHomePerspective ? match.home_score : match.away_score;
            var awayGoals = isHomePerspective ? match.away_score : match.home_score;
            var homeXg = isHomePerspective ? match.home_xg : match.away_xg;
            var awayXg = isHomePerspective ? match.away_xg : match.home_xg;

            summary.home.goalsFor += homeGoals;
            summary.home.goalsAgainst += awayGoals;
            summary.home.xgFor += homeXg;
            summary.away.goalsFor += awayGoals;
            summary.away.goalsAgainst += homeGoals;
            summary.away.xgFor += awayXg;

            if (awayGoals === 0) {
                summary.home.cleanSheets += 1;
            }

            if (homeGoals === 0) {
                summary.away.cleanSheets += 1;
            }

            if (homeGoals > awayGoals) {
                summary.home.wins += 1;
                summary.away.losses += 1;
            } else if (homeGoals < awayGoals) {
                summary.away.wins += 1;
                summary.home.losses += 1;
            } else {
                summary.home.draws += 1;
                summary.away.draws += 1;
            }
        });

        return summary;
    }

    function renderH2HTeamSummary(target, results, options) {
        var summary = summarizeH2H(results, options);
        var divisor = Math.max(summary.meetings, 1);
        var metricRows = [
            ['Wins', summary.home.wins, summary.away.wins],
            ['Draws', summary.home.draws, summary.away.draws],
            ['Goals Avg', (summary.home.goalsFor / divisor).toFixed(2), (summary.away.goalsFor / divisor).toFixed(2)],
            ['xG Avg', (summary.home.xgFor / divisor).toFixed(2), (summary.away.xgFor / divisor).toFixed(2)],
            ['Clean Sheets', summary.home.cleanSheets, summary.away.cleanSheets]
        ];

        target.innerHTML = [
            '<div class="sr-subheading">Team vs Team Summary</div>',
            '<div class="sr-compare-heading">',
            '<strong>' + escapeHtml(summary.homeTeamName) + '</strong>',
            '<span>Last ' + summary.meetings + ' meetings</span>',
            '<strong>' + escapeHtml(summary.awayTeamName) + '</strong>',
            '</div>',
            '<div class="sr-compare-list">',
            metricRows.map(function (row) {
                return [
                    '<div class="sr-compare-row">',
                    '<div class="sr-stat-label">' + escapeHtml(row[0]) + '</div>',
                    '<div class="sr-h2h-summary-values">',
                    '<strong>' + escapeHtml(String(row[1])) + '</strong>',
                    '<span>' + escapeHtml(row[0]) + '</span>',
                    '<strong>' + escapeHtml(String(row[2])) + '</strong>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function renderH2H(panel, options) {
        panel.__srH2HOptions = options;
        panel.__srH2HView = panel.__srH2HView || 'team';

        panel.innerHTML = [
            '<div class="sr-panel-heading">Head to Head</div>',
            '<div class="sr-toolbar" role="tablist" aria-label="Head to head views">',
            '<button type="button" class="sr-view-toggle sr-h2h-view-toggle' + (panel.__srH2HView === 'team' ? ' active' : '') + '" data-h2h-view="team" data-testid="widget-h2h-view-team" aria-selected="' + (panel.__srH2HView === 'team' ? 'true' : 'false') + '">Team Stats</button>',
            '<button type="button" class="sr-view-toggle sr-h2h-view-toggle' + (panel.__srH2HView === 'results' ? ' active' : '') + '" data-h2h-view="results" data-testid="widget-h2h-view-results" aria-selected="' + (panel.__srH2HView === 'results' ? 'true' : 'false') + '">Recent Results</button>',
            '<button type="button" class="sr-view-toggle sr-h2h-view-toggle' + (panel.__srH2HView === 'players' ? ' active' : '') + '" data-h2h-view="players" data-testid="widget-h2h-view-players" aria-selected="' + (panel.__srH2HView === 'players' ? 'true' : 'false') + '">Player vs Player</button>',
            '</div>',
            '<div class="sr-h2h-content" data-testid="widget-h2h-content"></div>'
        ].join('');

        panel.querySelectorAll('.sr-h2h-view-toggle').forEach(function (button) {
            button.addEventListener('click', function () {
                if (panel.__srH2HView === button.dataset.h2hView) {
                    return;
                }

                panel.__srH2HView = button.dataset.h2hView;
                renderH2H(panel, panel.__srH2HOptions || options);
            });
        });

        renderH2HContent(panel, panel.__srH2HOptions || options);
    }

    function renderH2HContent(panel, options) {
        var content = panel.querySelector('.sr-h2h-content');

        if (!content) {
            return;
        }

        if (panel.__srH2HView === 'team') {
            renderH2HTeamSummary(content, options.results || [], options);
            return;
        }

        if (panel.__srH2HView === 'results') {
            content.innerHTML = '<div class="sr-h2h-results"></div>';
            renderH2HResults(content.querySelector('.sr-h2h-results'), options.results || []);
            return;
        }

        content.innerHTML = [
            '<div class="sr-h2h-player-card">',
            '<div class="sr-h2h-selectors" data-testid="widget-h2h-selectors"></div>',
            '<div class="sr-h2h-player-comparison" data-testid="widget-h2h-player-comparison">' + renderInlineStatus('Choose two players to compare.', 'widget-h2h-empty') + '</div>',
            '</div>'
        ].join('');

        setupH2HPlayerSelector(
            content.querySelector('.sr-h2h-selectors'),
            content.querySelector('.sr-h2h-player-comparison'),
            options,
            panel
        );
    }

    function renderH2HResults(target, results) {
        target.innerHTML = [
            '<div class="sr-subheading">Recent Meetings</div>',
            '<div class="sr-h2h-results-list">',
            results.map(function (match) {
                var outcome = match.home_score > match.away_score ? 'W' : (match.home_score === match.away_score ? 'D' : 'L');

                return [
                    '<div class="sr-h2h-result-row">',
                    '<span class="sr-form-badge ' + getFormBadgeClass(outcome) + '">' + outcome + '</span>',
                    '<div>',
                    '<div class="sr-h2h-scoreline">' + escapeHtml(match.home_team) + ' ' + match.home_score + ' - ' + match.away_score + ' ' + escapeHtml(match.away_team) + '</div>',
                    '<div class="sr-h2h-meta">' + escapeHtml(match.match_date) + ' | xG ' + match.home_xg + ' - ' + match.away_xg + '</div>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function setupH2HPlayerSelector(selectorRoot, comparisonRoot, options, panel) {
        var homeSelect = document.createElement('select');
        var awaySelect = document.createElement('select');

        homeSelect.innerHTML = ['<option value="">Home player</option>'].concat(
            options.selectorData.home_players.map(function (player) {
                return '<option value="' + escapeHtml(player.player_id) + '">' + escapeHtml(player.name) + '</option>';
            })
        ).join('');

        awaySelect.innerHTML = ['<option value="">Away player</option>'].concat(
            options.selectorData.away_players.map(function (player) {
                return '<option value="' + escapeHtml(player.player_id) + '">' + escapeHtml(player.name) + '</option>';
            })
        ).join('');
        homeSelect.dataset.testid = 'widget-h2h-home-player';
        awaySelect.dataset.testid = 'widget-h2h-away-player';

        selectorRoot.innerHTML = '<div class="sr-subheading">Player Comparison</div>';
        selectorRoot.appendChild(homeSelect);
        selectorRoot.appendChild(awaySelect);

        if (panel && panel.__srSelectedHomePlayerId) {
            homeSelect.value = panel.__srSelectedHomePlayerId;
        }

        if (panel && panel.__srSelectedAwayPlayerId) {
            awaySelect.value = panel.__srSelectedAwayPlayerId;
        }

        async function updateComparison() {
            if (panel) {
                panel.__srSelectedHomePlayerId = homeSelect.value || '';
                panel.__srSelectedAwayPlayerId = awaySelect.value || '';
            }

            if (!homeSelect.value || !awaySelect.value) {
                comparisonRoot.innerHTML = renderInlineStatus(
                    'Choose two players to compare.',
                    'widget-h2h-empty'
                );
                return;
            }

            comparisonRoot.innerHTML = renderInlineStatus(
                'Loading comparison...',
                'widget-h2h-loading'
            );

            try {
                var url = options.apiBase + '/match/' + options.matchId + '/h2h/players?home_player_id=' +
                    encodeURIComponent(homeSelect.value) + '&away_player_id=' + encodeURIComponent(awaySelect.value);
                var response = await global.fetch(url);
                var payload = await response.json();
                renderPlayerComparison(comparisonRoot, payload.data);
            } catch (error) {
                comparisonRoot.innerHTML = renderInlineStatus(
                    'Unable to load player comparison.',
                    'widget-h2h-error',
                    'error'
                );
            }
        }

        homeSelect.addEventListener('change', updateComparison);
        awaySelect.addEventListener('change', updateComparison);
        updateComparison();
    }

    function renderPlayerComparison(target, data) {
        var stats = [
            ['goals', 'Goals'],
            ['assists', 'Assists'],
            ['xg', 'xG'],
            ['shots_per_game', 'Shots/Game'],
            ['pass_accuracy_pct', 'Pass Accuracy']
        ];

        target.innerHTML = [
            '<div class="sr-compare-heading">',
            '<strong>' + escapeHtml(data.home_player.name) + '</strong>',
            '<span>vs</span>',
            '<strong>' + escapeHtml(data.away_player.name) + '</strong>',
            '</div>',
            '<div class="sr-compare-list">',
            stats.map(function (entry) {
                var key = entry[0];
                var label = entry[1];
                var homeValue = Number(data.home_player[key]);
                var awayValue = Number(data.away_player[key]);
                var maxValue = Math.max(homeValue, awayValue, 1);

                return [
                    '<div class="sr-compare-row">',
                    '<div class="sr-stat-label">' + escapeHtml(label) + '</div>',
                    '<div class="sr-compare-bars">',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-home" style="width: ' + ((homeValue / maxValue) * 100) + '%;"></div></div>',
                    '<span>' + homeValue + ' / ' + awayValue + '</span>',
                    '<div class="sr-stat-bar"><div class="sr-stat-fill is-away" style="width: ' + ((awayValue / maxValue) * 100) + '%;"></div></div>',
                    '</div>',
                    '</div>'
                ].join('');
            }).join(''),
            '</div>'
        ].join('');
    }

    function renderFactsList(target, facts) {
        target.innerHTML = facts.map(function (fact) {
            return '<li class="sr-fact-item" data-category="' + escapeHtml(fact.category) + '">' +
                '<span class="sr-fact-category">' + escapeHtml(fact.category) + '</span>' +
                '<span>' + escapeHtml(fact.text) + '</span>' +
                '</li>';
        }).join('');
    }

    function applyFactsFilter(panel, filter) {
        panel.__srFactsFilter = filter;
        panel.querySelectorAll('.sr-facts-filter').forEach(function (button) {
            button.classList.toggle('active', button.dataset.category === filter);
        });

        panel.querySelectorAll('.sr-fact-item').forEach(function (item) {
            item.hidden = filter !== 'all' && item.dataset.category !== filter;
        });
    }

    function mergeFacts(previousFacts, nextFacts) {
        if (!Array.isArray(previousFacts) || !previousFacts.length) {
            return nextFacts.slice();
        }

        var seen = {};
        var merged = [];

        nextFacts.forEach(function (fact) {
            seen[fact.fact_id] = true;
            merged.push(fact);
        });

        previousFacts.forEach(function (fact) {
            if (!seen[fact.fact_id]) {
                merged.push(fact);
            }
        });

        return merged;
    }

    function renderMatchFacts(panel, facts, context) {
        panel.__srAllFacts = Array.isArray(facts) ? facts.slice() : [];

        var visibleFacts = panel.__srAllFacts.filter(function (fact) {
            if (fact.category !== 'live') {
                return true;
            }

            if (!context || !isInPlayPhase(context.phase)) {
                return false;
            }

            if (context.phase === 'FULL_TIME') {
                return true;
            }

            return typeof fact.minute !== 'number' || fact.minute <= Number(context.clock);
        });

        var mergedFacts = isInPlayPhase(context && context.phase)
            ? mergeFacts(panel.__srFactsData || [], visibleFacts)
            : visibleFacts;

        panel.__srFactsData = mergedFacts;

        panel.innerHTML = [
            '<div class="sr-panel-heading">Match Facts and Commentary</div>',
            '<div class="sr-toolbar">',
            '<button type="button" class="sr-facts-filter active" data-category="all" data-testid="widget-facts-filter-all">All</button>',
            '<button type="button" class="sr-facts-filter" data-category="team">Team</button>',
            '<button type="button" class="sr-facts-filter" data-category="player">Player</button>',
            '<button type="button" class="sr-facts-filter" data-category="match">Match</button>',
            '<button type="button" class="sr-facts-filter" data-category="live" data-testid="widget-facts-filter-live">Live</button>',
            '</div>',
            '<ul class="sr-facts-list" data-testid="widget-facts-list"></ul>'
        ].join('');

        renderFactsList(panel.querySelector('.sr-facts-list'), mergedFacts);

        panel.querySelectorAll('.sr-facts-filter').forEach(function (button) {
            button.addEventListener('click', function () {
                applyFactsFilter(panel, button.dataset.category);
            });
        });

        applyFactsFilter(panel, panel.__srFactsFilter || 'all');
    }

    function renderGroupedPlayers(players) {
        var groups = { GK: [], DEF: [], MID: [], FWD: [] };

        players.forEach(function (player) {
            groups[normalizeSquadGroup(player.position)].push(player);
        });

        return Object.keys(groups).map(function (group) {
            if (!groups[group].length) {
                return '';
            }

            return [
                '<div class="sr-squad-group"><strong>' + group + '</strong></div>',
                '<ul class="sr-player-list">',
                groups[group].map(function (player) {
                    return '<li>' + player.number + ' ' + escapeHtml(player.name) + ' <span>' + escapeHtml(player.position) + '</span></li>';
                }).join(''),
                '</ul>'
            ].join('');
        }).join('');
    }

    function renderBenchList(team) {
        return [
            '<div class="sr-squad-group"><strong>Bench</strong></div>',
            '<ul class="sr-player-list">',
            team.bench.map(function (player) {
                return '<li>' + player.number + ' ' + escapeHtml(player.name) + ' <span>' + escapeHtml(player.position) + '</span></li>';
            }).join(''),
            '</ul>'
        ].join('');
    }

    function renderFullSquadColumn(team) {
        var combinedPlayers = team.starting_xi.concat(team.bench).slice().sort(function (a, b) {
            return a.number - b.number;
        });

        return [
            '<section class="sr-squad-card">',
            '<div class="sr-subheading">' + escapeHtml(team.team_name) + ' Squad</div>',
            '<div class="sr-status-copy">Line-ups not confirmed yet.</div>',
            renderGroupedPlayers(combinedPlayers),
            '</section>'
        ].join('');
    }

    function renderSquads(panel, data, context) {
        panel.__srSquadsData = data;

        if (context && context.pageType === 'match' && isInPlayPhase(context.phase)) {
            panel.dataset.viewState = 'live-formation';
            renderPitchView(panel, context);
            return;
        }

        if (context && context.lineupsConfirmed) {
            panel.dataset.viewState = 'confirmed-lineups';
            renderConfirmedLineups(panel, data, context);
            return;
        }

        panel.dataset.viewState = 'pre-match-squad';

        panel.innerHTML = [
            '<div class="sr-panel-heading">Squads and Line-ups</div>',
            '<div class="sr-squads-grid" data-testid="widget-squads-pre-match">',
            renderFullSquadColumn(data.home),
            renderFullSquadColumn(data.away),
            '</div>'
        ].join('');
    }

    function renderConfirmedSquadColumn(team) {
        return [
            '<section class="sr-squad-card">',
            '<div class="sr-subheading">' + escapeHtml(team.team_name) + ' (' + escapeHtml(team.formation) + ')</div>',
            '<div class="sr-status-copy">Confirmed XI</div>',
            '<div class="sr-squad-group"><strong>Confirmed XI</strong></div>',
            renderGroupedPlayers(team.starting_xi),
            renderBenchList(team),
            '</section>'
        ].join('');
    }

    function renderConfirmedLineups(panel, data, context) {
        var usePitchView = !context || context.lineupView !== 'list';
        panel.dataset.viewState = 'confirmed-lineups';

        if (!usePitchView) {
            panel.innerHTML = [
                '<div class="sr-panel-heading">Confirmed Line-ups</div>',
                '<div class="sr-squads-grid" data-testid="widget-squads-confirmed-list">',
                renderConfirmedSquadColumn(data.home),
                renderConfirmedSquadColumn(data.away),
                '</div>'
            ].join('');
            return;
        }

        panel.innerHTML = [
            '<div class="sr-panel-heading">Confirmed Line-ups</div>',
            '<div class="sr-status-copy sr-status-copy--spaced">Starting XIs are confirmed. Bench players remain listed below each pitch.</div>',
            '<div class="sr-pitch-grid" data-testid="widget-squads-confirmed-pitch">',
            renderPitchTeam(data.home, { showEvents: false, includeBench: true }),
            renderPitchTeam(data.away, { showEvents: false, includeBench: true }),
            '</div>'
        ].join('');
    }

    function renderPitchView(panel, context) {
        var data = panel.__srSquadsData;
        panel.dataset.viewState = 'live-formation';

        if (!data) {
            panel.innerHTML = renderInlineStatus('Pitch view is not ready yet.', 'widget-squads-live-empty');
            return;
        }

        panel.innerHTML = [
            '<div class="sr-panel-heading">Live Formation View</div>',
            '<div class="sr-live-events-summary" data-testid="widget-squads-live-events">',
            renderLiveEventSummary(data.home, context),
            renderLiveEventSummary(data.away, context),
            '</div>',
            '<div class="sr-pitch-grid" data-testid="widget-squads-live-pitch">',
            renderPitchTeam(data.home, { showEvents: true, context: context }),
            renderPitchTeam(data.away, { showEvents: true, context: context }),
            '</div>'
        ].join('');
    }

    function renderLiveEventSummary(team, context) {
        var events = getVisibleLiveEvents(team, context);

        if (!events.length) {
            return [
                '<section class="sr-live-events-card">',
                '<div class="sr-subheading">' + escapeHtml(team.team_name) + ' Live Events</div>',
                '<div class="sr-tab-placeholder">No key events yet.</div>',
                '</section>'
            ].join('');
        }

        return [
            '<section class="sr-live-events-card">',
            '<div class="sr-subheading">' + escapeHtml(team.team_name) + ' Live Events</div>',
            '<ul class="sr-live-event-list">',
            events.map(function (event) {
                var player = team.starting_xi.concat(team.bench).find(function (entry) {
                    return entry.player_id === event.player_id;
                });
                var playerName = player ? player.name : event.player_id;

                return '<li><span class="sr-live-event-badge is-' + escapeHtml(event.type) + '">' +
                    escapeHtml(event.label) + '</span><span>' + escapeHtml(playerName) +
                    ' (' + escapeHtml(String(event.minute)) + '\')</span></li>';
            }).join(''),
            '</ul>',
            '</section>'
        ].join('');
    }

    function renderPitchTeam(team, options) {
        var resolvedOptions = Object.assign(
            {
                showEvents: true,
                includeBench: false,
                context: null
            },
            options || {}
        );
        var liveEvents = getVisibleLiveEvents(team, resolvedOptions.context);

        function renderPlayerEventBadges(playerId) {
            if (!resolvedOptions.showEvents) {
                return '';
            }

            var events = liveEvents.filter(function (event) {
                return event.player_id === playerId;
            });

            if (!events.length) {
                return '';
            }

            return '<div class="sr-player-event-stack">' + events.map(function (event) {
                return '<span class="sr-live-event-badge is-' + escapeHtml(event.type) + '">' +
                    escapeHtml(event.label) + '</span>';
            }).join('') + '</div>';
        }

        return [
            '<section class="sr-pitch-card">',
            '<div class="sr-subheading">' + escapeHtml(team.team_name) + ' (' + escapeHtml(team.formation) + ')</div>',
            '<div class="sr-pitch-surface">',
            team.starting_xi.map(function (player) {
                return '<div class="sr-player-node" style="left: ' + player.position_x + '%; top: ' + player.position_y + '%;">' +
                    renderPlayerEventBadges(player.player_id) +
                    '<span>' + player.number + '</span><small>' + escapeHtml(player.name) + '</small>' +
                '</div>';
            }).join(''),
            '</div>',
            resolvedOptions.includeBench ? renderBenchList(team) : '',
            '</section>'
        ].join('');
    }

    global.renderPitchView = renderPitchView;
    global.SRRenderers = {
        renderLeagueTable: renderLeagueTable,
        renderFixtures: renderFixtures,
        renderTeamStats: renderTeamStats,
        renderH2H: renderH2H,
        renderMatchFacts: renderMatchFacts,
        renderSquads: renderSquads,
        renderPitchView: renderPitchView
    };
}(window));
