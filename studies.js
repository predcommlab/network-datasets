// Network datasets — data
//
// This is the only file you normally edit to add or update a dataset.
// To add one: copy a { ... } block, change the fields, save, then commit
// and push:  git add studies.js && git commit -m "..." && git push
//
// Fields per dataset:
//   id           short slug (matches about/studies/<id>.md)
//   name         short display name (NOT the paper title)
//   authors      author names, as a string
//   institution  where the work was done
//   external     true if the authors are outside the lab
//   year         publication year, or null
//   published    true / false
//   repo         URL to where the data is stored, or null
//   doi          DOI string, or null
//   paper        published paper title (optional; shown for published ones)
//   species, modality, technique, ...  facet values, each an ARRAY so a
//     dataset can carry several (e.g. technique:["EEG","Behavioural responses"]).
//     Allowed values are listed in about/catalogue_labels.md.

const STUDIES = [
  {id:"statements-written", name:"Statements (Written)", authors:"Philipp Schumann", institution:"UKE / RUB", external:false,
   year:null, published:false, repo:null, doi:null,
   species:["Human"], modality:["Visual"], technique:["Behavioural responses"]},
  {id:"voicepriors-behaviour", name:"Voice Priors (behavioural)", authors:"Carina Ufer", institution:"RUB", external:false,
   year:null, published:false, repo:null, doi:null,
   species:["Human"], modality:["Auditory"], technique:["Behavioural responses"]},
  {id:"voicepriors-eeg", name:"Voice Priors (EEG)", authors:"Janika Becker", institution:"RUB", external:false,
   year:null, published:false, repo:null, doi:null,
   species:["Human"], modality:["Auditory"], technique:["EEG","Behavioural responses"]},
  {id:"statements-voiced", name:"Statements (Voiced)", authors:"Nele Pfitzner", institution:"RUB / Oldenburg", external:false,
   year:null, published:false, repo:null, doi:null,
   species:["Human"], modality:["Auditory"], technique:["Behavioural responses"]},
  {id:"voicerating-prestudy", name:"Voice Rating Pre-study", authors:"Nele Pfitzner", institution:"RUB / Oldenburg", external:false,
   year:null, published:false, repo:null, doi:null,
   species:["Human"], modality:["Auditory"], technique:["Behavioural responses"]},
  {id:"prederror-greve2018", name:"Prediction-error & schema memory (Greve et al. 2018)", authors:"Greve, Cooper, Tibon & Henson", institution:"MRC-CBU, Cambridge", external:true,
   year:"2018", published:true, repo:"https://osf.io/x692m/", doi:"10.1037/xge0000498",
   paper:"Knowledge is power: prior knowledge aids memory for both congruent and incongruent events, but in different ways",
   species:["Human"], modality:["Visual"], technique:["Behavioural responses"]}
];
