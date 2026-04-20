const FLOAT_PHASE_BASE = Object.freeze([0.33, 0.26, 0.2, 0.13, 0.08]);
const DRAW_PHASE_BASE = Object.freeze([0.08, 0.14, 0.22, 0.26, 0.3]);
const BOOK_MARGIN = 0.9;

function clamp01(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0.5;
  return Math.min(1, Math.max(0, parsed / 100));
}

function normalize(weights, fallback) {
  const safe =
    Array.isArray(weights) && weights.length === fallback.length
      ? weights.map((value, index) => {
          const parsed = Number(value);
          return Number.isFinite(parsed) && parsed > 0
            ? parsed
            : fallback[index];
        })
      : [...fallback];

  const sum = safe.reduce((total, current) => total + current, 0);
  if (!sum) return Object.freeze([...fallback]);

  return Object.freeze(safe.map((value) => value / sum));
}

function createCharacterAdjustedBases(character) {
  if (!character) {
    return {
      floatBase: [...FLOAT_PHASE_BASE],
      drawBase: [...DRAW_PHASE_BASE],
    };
  }
  const stamina = clamp01(character.stamina);
  const control = clamp01(character.control);
  const power = clamp01(character.power);

  const floatBase = FLOAT_PHASE_BASE.map((base, index) => {
    const earlyPhaseWeight = 1 - index / 4;
    const latePhaseWeight = index / 4;
    const modifier =
      1 +
      (stamina - 0.5) * earlyPhaseWeight * 0.9 +
      (power - 0.5) * latePhaseWeight * 0.8;
    return Math.max(0.0001, base * modifier);
  });

  const drawBase = DRAW_PHASE_BASE.map((base, index) => {
    const lateDrawWeight = index / 4;
    const earlyDrawWeight = 1 - lateDrawWeight;
    const modifier =
      1 +
      (control - 0.5) * lateDrawWeight * 0.9 +
      (power - 0.5) * earlyDrawWeight * 0.5;
    return Math.max(0.0001, base * modifier);
  });

  return {
    floatBase: normalize(floatBase, FLOAT_PHASE_BASE),
    drawBase: normalize(drawBase, DRAW_PHASE_BASE),
  };
}

function toOdds(probability) {
  if (!probability || probability <= 0) return 1.01;
  const odds = (1 / probability) * BOOK_MARGIN;
  return Number(Math.max(1.01, odds).toFixed(2));
}

function createBoard(input = {}) {
  const floatBase = normalize(input.floatBase, FLOAT_PHASE_BASE);
  const drawBase = normalize(input.drawBase, DRAW_PHASE_BASE);
  const rawCombos = [];

  for (let floatPhase = 1; floatPhase <= 5; floatPhase += 1) {
    for (let drawPhase = floatPhase + 1; drawPhase <= 5; drawPhase += 1) {
      rawCombos.push({
        floatPhase,
        drawPhase,
        key: `F${floatPhase}andD${drawPhase}`,
        rawProbability: floatBase[floatPhase - 1] * drawBase[drawPhase - 1],
      });
    }
  }

  const totalRaw = rawCombos.reduce(
    (sum, combo) => sum + combo.rawProbability,
    0,
  );
  const comboProbabilities = rawCombos.map((combo) => ({
    ...combo,
    probability: combo.rawProbability / totalRaw,
  }));

  const floatMarginals = { F1: 0, F2: 0, F3: 0, F4: 0, F5: 0 };
  const drawMarginals = { D1: 0, D2: 0, D3: 0, D4: 0, D5: 0 };

  for (const combo of comboProbabilities) {
    floatMarginals[`F${combo.floatPhase}`] += combo.probability;
    drawMarginals[`D${combo.drawPhase}`] += combo.probability;
  }

  const singles = {
    draw: Object.keys(drawMarginals).map((key) => ({
      key,
      odds: toOdds(drawMarginals[key]),
      probability: drawMarginals[key],
    })),
    float: Object.keys(floatMarginals).map((key) => ({
      key,
      odds: toOdds(floatMarginals[key]),
      probability: floatMarginals[key],
    })),
  };

  const doublesByFloat = { F1: [], F2: [], F3: [], F4: [], F5: [] };
  const doublesFlat = [];

  for (const combo of comboProbabilities) {
    const entry = {
      key: combo.key,
      odds: toOdds(combo.probability),
      probability: combo.probability,
      floatPhase: combo.floatPhase,
      drawPhase: combo.drawPhase,
    };
    doublesByFloat[`F${combo.floatPhase}`].push(entry);
    doublesFlat.push(entry);
  }

  const orderedSingle = [...singles.draw, ...singles.float];
  const orderedDouble = [
    ...doublesByFloat.F1,
    ...doublesByFloat.F2,
    ...doublesByFloat.F3,
    ...doublesByFloat.F4,
    ...doublesByFloat.F5,
  ];

  return Object.freeze({
    singles: Object.freeze(singles),
    doublesByFloat: Object.freeze(doublesByFloat),
    allOptions: Object.freeze([
      ...orderedSingle.map((item) => item.key),
      ...orderedDouble.map((item) => item.key),
    ]),
    oddsByOption: Object.freeze(
      Object.fromEntries(
        [...orderedSingle, ...orderedDouble].map((item) => [
          item.key,
          item.odds,
        ]),
      ),
    ),
    comboDistribution: Object.freeze(doublesFlat),
  });
}

function createBoardForCharacter(character) {
  const adjusted = createCharacterAdjustedBases(character);
  return createBoard(adjusted);
}

const board = createBoard();

module.exports = { board, createBoardForCharacter };
