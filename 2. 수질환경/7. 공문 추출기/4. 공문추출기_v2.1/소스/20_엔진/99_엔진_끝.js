/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   [20_엔진/99_엔진_끝.js] 엔진 끝 — 밖으로 내보내는 이름
   하는 일 : 화면·시험에서 쓰는 이름 목록. 새 함수를 화면에서 쓰려면 여기에 이름을 더한다.
   주요 이름: API, ENGINE_VERSION
   이럴 때 고침: 엔진 함수를 화면에서 새로 쓸 때
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

const _internal = { parseXML, kids, walk, findAll, has, textAll, inlineText, blockLines, squash, spacedName, buildGrid, rowOrigins, classify,
  pickSampleCol, readSampleTable, findSampleTables, expandNo, parseItems, normItem, parseDate, allDates, dateFromBody, unzipEntry, unzipBytes, unzipList,
  buildResult, rebuildResult, looksLikeSampleNo, refreshStdText, hesc, b64 };
const ENGINE_VERSION = '2.1';
const API = { _internal, rebuildResult, unzipList, extractOdt, unzipBytes, renderOdtHtml, markDuplicates, parseXML, parseDate, expandNo, parseItems, COLUMNS, ITEM_DICT, ORG_EXCEPTIONS,
  parseStdTable, applyStdTable, lookupStd, missingStdPairs, readXlsxRows, decodeText, parseCsv,
  parseHwpx, hwpGrid, hwpxHtml, attachmentNames, attachScore, samplesFromAttachments, samplesFromManual, parsePastedSamples,
  isReply, parseReply, pdfLines, parseReportPage, parseReportPdf, normReportItem, matchReply, matchReport, noKey, orgOk,
  STD_DAYS, stdDaysTable, deadline, remaining, sampleDeadline, isWorkday, ymd, toDate, addDays,
  HOLIDAYS_BUILTIN, parseHolidayJson, safeName, caseFolderName,
  VERSION: ENGINE_VERSION };
// 화면 코드는 OdtEngine(E)·OdtEngine2(E2) 두 이름으로 부르므로 같은 묶음을 두 이름으로 내보낸다
if (typeof module !== 'undefined' && module.exports) module.exports = API; else { global.OdtEngine = API; global.OdtEngine2 = API; }
})(typeof window !== 'undefined' ? window : globalThis);
