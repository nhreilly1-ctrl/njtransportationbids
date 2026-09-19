const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const template = fs.readFileSync('app/templates/base.html', 'utf8');
const start = template.indexOf('  function analyticsParams');
const script = template.slice(start, template.indexOf('</script>', start));
const handlers = {};
const events = [];
const gtag = (...args) => events.push(args);
vm.runInNewContext(script, {
  document: {addEventListener: (name, fn) => handlers[name] = fn},
  window: {gtag}, gtag,
  FormData: class { constructor(form) {this.form = form;} get(key) {return this.form.fields[key];} },
});
const form = {tagName: 'FORM', dataset: {analyticsEvent: 'filter_applied', surface: 'construction'}, fields: {county: 'Morris', q: 'bridge'}};
const event = {target: {closest: () => form}};
handlers.click(event);
assert.equal(events.length, 0, 'Clicking a form field is not applying a filter');
handlers.submit(event);
assert.equal(events.length, 1);
assert.equal(events[0][1], 'filter_applied');
assert.equal(events[0][2].filter_county, 'Morris');
assert.equal(events[0][2].has_keyword, true);
assert.equal(events[0][2].filter_q, undefined);
handlers.click({target: {closest: () => ({tagName: 'A', dataset: {analyticsEvent: 'map_click', noticeId: 'test'}})}});
assert.equal(events.length, 2);
assert.equal(events[1][1], 'map_click');
handlers.click({target: {closest: () => ({tagName: 'A', dataset: {
  analyticsEvent: 'project_research_click', noticeId: 'research-test', agency: 'NJDOT',
  opportunityType: 'construction', resource: 'traffic_cameras', resourceStage: 'road',
  surface: 'opportunity_detail'
}})}});
assert.equal(events.length, 3);
assert.equal(events[2][1], 'project_research_click');
assert.equal(events[2][2].resource, 'traffic_cameras');
assert.equal(events[2][2].resource_stage, 'road');
assert.equal(events[2][2].notice_id, 'research-test');
assert.equal(events[2][2].opportunity_type, 'construction');
assert.equal(events[2][2].surface, 'opportunity_detail');
for (const path of ['app/templates/opportunity_list.html', 'app/templates/notices/notice_list.html']) {
  const html = fs.readFileSync(path, 'utf8');
  assert.ok(!html.includes('this.form.submit()'));
  assert.ok(html.includes('this.form.requestSubmit()'));
}
console.log('Analytics interaction tests passed; no requests sent.');
