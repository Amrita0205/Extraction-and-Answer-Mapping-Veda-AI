import type { JobStatus, Question, UnmatchedAnswer } from "./types";

/**
 * The fixture the app serves when NEXT_PUBLIC_API_BASE is unset.
 *
 * It is built to contain every awkward case the brief names, so the UI states
 * can be reviewed without a backend:
 *
 *   - Q3 is answered ABOVE Q2 on page 1        (out of order)
 *   - 11(a) and 11(b) are separate entries      (labelled sub-parts)
 *   - 11(b)'s answer runs from page 2 onto 3    (spans multiple pages)
 *   - Q4, Q6-Q10 and Q12 have no answer         (unanswered)
 *   - a stray "Q14" exists on a 12-question paper (matches nothing)
 *
 * The regions below are the exact coordinates `spike/make_mock_pages.py` draws
 * the mock handwriting at, so the highlight visibly lands on the right block.
 */

const q = (
  id: string,
  number: string,
  part: string | null,
  text: string,
  marks: number,
  order: number,
  extra: Partial<Question> = {},
): Question => ({
  id,
  number,
  part,
  text,
  marks,
  order,
  status: "unanswered",
  answer: null,
  grade: {
    awarded: 0,
    max: marks,
    verdict: "ungraded",
    feedback: "This question was left unanswered.",
  },
  ...extra,
});

const questions: Question[] = [
  q(
    "q_1",
    "1",
    null,
    "Which blood vessel carries blood away from the heart?",
    2,
    0,
    {
      status: "answered",
      answer: {
        id: "a_0_0",
        text: "The artery carries blood away from the heart. The aorta is the largest artery.",
        regions: [{ page: 0, x0: 0.065, y0: 0.1, x1: 0.9, y1: 0.275 }],
        confidence: 0.97,
        match_method: "label",
        spans_pages: false,
      },
      grade: {
        awarded: 2,
        max: 2,
        verdict: "correct",
        feedback:
          "Correct — arteries carry blood away from the heart, and naming the aorta as the largest shows good recall.",
      },
    },
  ),
  q(
    "q_2",
    "2",
    null,
    "Which of the following organelles is primarily involved in photosynthesis?",
    2,
    1,
    {
      status: "answered",
      answer: {
        id: "a_0_2",
        text: "The chloroplast. It contains chlorophyll which absorbs light energy.",
        regions: [{ page: 0, x0: 0.065, y0: 0.57, x1: 0.88, y1: 0.78 }],
        confidence: 0.97,
        match_method: "label",
        spans_pages: false,
      },
      grade: {
        awarded: 2,
        max: 2,
        verdict: "correct",
        feedback:
          "Excellent work! You correctly identified the chloroplast as the organelle responsible for photosynthesis. Keep it up!",
      },
    },
  ),
  q(
    "q_3",
    "3",
    null,
    "Explain the role of chloroplasts in photosynthesis, naming the main pigments involved and briefly outlining the two major stages of the process.",
    2,
    2,
    {
      status: "answered",
      answer: {
        id: "a_0_1",
        text: "The process mainly occurs in the chloroplast of the plant cell. It has two main stages: 1. Light reaction — captures light energy. 2. Dark reaction — uses energy to make glucose.",
        regions: [{ page: 0, x0: 0.065, y0: 0.33, x1: 0.9, y1: 0.515 }],
        confidence: 0.97,
        match_method: "label",
        spans_pages: false,
      },
      grade: {
        awarded: 2,
        max: 2,
        verdict: "correct",
        feedback:
          "Both stages are named correctly and in the right order. Naming chlorophyll a and b explicitly would make this airtight.",
      },
    },
  ),
  q(
    "q_4",
    "4",
    null,
    "Describe the flow of blood through the human heart starting from the right atrium and ending at the aorta; include the names of valves crossed.",
    2,
    3,
  ),
  q(
    "q_5",
    "5",
    null,
    "Draw a labelled diagram of an alveolus showing capillaries and air space (label alveolar sac, capillary, and direction of gas exchange).",
    2,
    4,
    {
      status: "answered",
      answer: {
        id: "a_2_2",
        text: "[diagram of an alveolus] Labels: alveolar sac, capillary, oxygen in, carbon dioxide out.",
        regions: [{ page: 2, x0: 0.065, y0: 0.6, x1: 0.86, y1: 0.85 }],
        confidence: 0.97,
        match_method: "label",
        spans_pages: false,
      },
      grade: {
        awarded: 2,
        max: 2,
        verdict: "correct",
        feedback:
          "Clear diagram with all three labels present and the direction of gas exchange marked.",
      },
    },
  ),
  q(
    "q_6",
    "6",
    null,
    "Draw a neat labelled diagram of the human digestive system (stomach, small intestine, large intestine, liver, pancreas) and label the site where most absorption occurs.",
    5,
    5,
  ),
  q(
    "q_7",
    "7",
    null,
    "Draw and label a nephron (Bowman's capsule, glomerulus, proximal tubule, loop of Henle, distal tubule, collecting duct).",
    5,
    6,
  ),
  q(
    "q_8",
    "8",
    null,
    "Explain the structural differences between palisade mesophyll and spongy mesophyll and state how each structure aids its function in the leaf.",
    5,
    7,
  ),
  q(
    "q_9",
    "9",
    null,
    "Describe the process of transpiration in plants in two to three sentences and name two environmental factors that increase its rate.",
    5,
    8,
  ),
  q(
    "q_10",
    "10",
    null,
    "Explain how the structure of xylem vessels facilitates water transport in plants (mention one structural feature and its role).",
    5,
    9,
  ),
  q(
    "q_11_a",
    "11",
    "a",
    "A diagram shows two potted plants — Plant A in bright light with broad green leaves, Plant B kept in dim light with pale, elongated leaves. Explain the difference.",
    2,
    10,
    {
      status: "answered",
      answer: {
        id: "a_1_0",
        text: "Plant B has less light so it makes less chlorophyll and the leaves stay pale. The stem grows long to reach the light.",
        regions: [{ page: 1, x0: 0.065, y0: 0.08, x1: 0.87, y1: 0.22 }],
        confidence: 0.97,
        match_method: "label",
        spans_pages: false,
      },
      grade: {
        awarded: 2,
        max: 2,
        verdict: "correct",
        feedback:
          "You linked low light to reduced chlorophyll and to etiolation. That is exactly the reasoning asked for.",
      },
    },
  ),
  q(
    "q_11_b",
    "11",
    "b",
    "Suggest one practical measure to help Plant B recover.",
    3,
    11,
    {
      status: "answered",
      answer: {
        id: "a_1_1",
        text: "Move Plant B to a place with more sunlight, like near a window. Then it will get light and make chlorophyll again and the leaves become green. Also water it properly and use some fertiliser so it grows healthy.",
        // Written at the foot of page 2 and finished at the top of page 3.
        regions: [
          { page: 1, x0: 0.065, y0: 0.27, x1: 0.9, y1: 0.915 },
          { page: 2, x0: 0.065, y0: 0.06, x1: 0.88, y1: 0.3 },
        ],
        confidence: 0.94,
        match_method: "label",
        spans_pages: true,
      },
      grade: {
        awarded: 1,
        max: 3,
        verdict: "partial",
        feedback:
          "Moving the plant into better light is the right measure. The marks were for one measure explained precisely — the extra points about water and fertiliser do not address the light problem the question is about.",
      },
    },
  ),
  q(
    "q_12",
    "12",
    null,
    "A resting person has a tidal volume (air per breath) of 0.5 L and breathes 12 times per minute. Calculate the pulmonary ventilation rate. Show working.",
    5,
    12,
  ),
];

const unmatched: UnmatchedAnswer[] = [
  {
    id: "a_2_1",
    label: "Q14.",
    text: "Osmosis is the movement of water from a dilute solution to a concentrated solution through a semi-permeable membrane.",
    regions: [{ page: 2, x0: 0.065, y0: 0.36, x1: 0.85, y1: 0.55 }],
    matched_question_id: null,
    match_method: "none",
    confidence: 0,
  },
];

const answered = questions.filter((item) => item.status === "answered");

export const mockJob: JobStatus = {
  job_id: "mock",
  status: "done",
  stage: "done",
  progress: 1,
  message: "Ready",
  error: null,
  result: {
    questions,
    unmatched_answers: unmatched,
    question_pages: [],
    answer_pages: [0, 1, 2].map((index) => ({
      index,
      width: 900,
      height: 1200,
      url: `/mock/answer-${index}.png`,
    })),
    summary: {
      total_questions: questions.length,
      answered: answered.length,
      unanswered: questions.length - answered.length,
      unmatched_answers: unmatched.length,
      marks_awarded: questions.reduce((sum, item) => sum + (item.grade?.awarded ?? 0), 0),
      marks_total: questions.reduce((sum, item) => sum + (item.marks ?? 0), 0),
      graded: true,
      overall_feedback:
        "You have a solid grasp of photosynthesis and gas exchange, and your diagrams are labelled carefully. The clearest thing to work on next is answering the question that was actually asked — 11(b) asked for one measure, and the extra material cost marks rather than earning them.",
    },
    warnings: [
      "1 answer did not correspond to any question on the paper (Q14.).",
    ],
  },
};
