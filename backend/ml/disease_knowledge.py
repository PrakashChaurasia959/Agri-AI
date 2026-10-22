"""Educational disease knowledge base.

Each entry maps a PlantVillage class to the crop, the disease, the visible
symptoms and the generally recommended prevention / care steps.

Two things this module deliberately does **not** do:

* It does not present model output as a diagnosis.  The content is generic,
  publicly documented agronomic guidance and it is always presented together
  with a recommendation to confirm with a qualified agricultural extension
  officer or agronomist.
* It does not invent entries for classes that were never observed during
  training.  Unknown labels produce an explicit uncertainty response.

Source of the underlying plant pathology descriptions: standard agricultural
extension literature (e.g. university extension fact sheets on apple scab,
late blight, huanglongbing and downy/powdery mildews).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

GENERAL_DISCLAIMER = (
    "This is an AI-generated estimate based on a single leaf image, not a "
    "laboratory diagnosis. Image quality, crop variety, lighting and diseases "
    "absent from the training set can change the result. Confirm with a "
    "qualified agricultural extension officer or agronomist before acting."
)

UNCERTAINTY_MESSAGE = (
    "The model was not confident enough about this image to identify a specific "
    "disease. Re-shoot the leaf in good, even light with the camera steady, "
    "keep the whole leaf in frame, and try again. If the symptoms persist, "
    "consult a qualified agricultural extension officer."
)


@dataclass(frozen=True)
class DiseaseEntry:
    """Educational information for one class."""

    class_name: str
    crop: str
    disease: str
    is_healthy: bool = False
    symptoms: list[str] = field(default_factory=list)
    prevention: list[str] = field(default_factory=list)
    treatment: list[str] = field(default_factory=list)
    severity: str = "moderate"

    @property
    def display_name(self) -> str:
        if self.is_healthy:
            return f"{self.crop} - healthy"
        return f"{self.crop} - {self.disease}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "crop": self.crop,
            "disease": None if self.is_healthy else self.disease,
            "display_name": self.display_name,
            "is_healthy": self.is_healthy,
            "symptoms": list(self.symptoms),
            "prevention": list(self.prevention),
            "treatment": list(self.treatment),
            "severity": self.severity,
            "disclaimer": GENERAL_DISCLAIMER,
        }


def _entry(
    class_name: str,
    crop: str,
    disease: str,
    *,
    healthy: bool = False,
    severity: str = "moderate",
    symptoms: list[str] | None = None,
    prevention: list[str] | None = None,
    treatment: list[str] | None = None,
) -> DiseaseEntry:
    return DiseaseEntry(
        class_name=class_name,
        crop=crop,
        disease=disease,
        is_healthy=healthy,
        symptoms=symptoms or [],
        prevention=prevention or [],
        treatment=treatment or [],
        severity=severity,
    )


_HEALTHY_GENERIC = {
    "symptoms": [
        "Uniform leaf colour with no spots, blotches, powdery growth or necrotic tissue",
        "Normal leaf shape and colour across the visible foliage",
    ],
    "prevention": [
        "Continue routine scouting at regular intervals through the season",
        "Maintain good airflow and balanced nutrition",
        "Keep field sanitation: remove infected residues and monitor neighbouring plots",
    ],
    "treatment": [
        "No disease treatment is indicated for this class",
        "Keep scouting for early symptoms and re-check after weather events",
    ],
}


CLASSES: list[DiseaseEntry] = [
    # ---------------------------------------------------------------- Apple
    _entry(
        "Apple___Apple_scab",
        "Apple",
        "Apple scab (Venturia inaequalis)",
        severity="moderate",
        symptoms=[
            "Olive-green to dark brown velvety spots on the upper leaf surface",
            "Spots are often irregular and develop a feathery, blurred margin",
            "Infected leaves curl, distort, yellow and drop prematurely",
            "Dark corky scabs form on the fruit surface and may crack",
        ],
        prevention=[
            "Choose scab-resistant cultivars where available",
            "Prune the canopy for good air movement and light penetration",
            "Remove and destroy fallen leaves - the fungus overwinters there",
            "Avoid overhead irrigation and irrigate early in the day",
        ],
        treatment=[
            "Protectant and systemic fungicides (for example captan, mancozeb or myclobutanil) "
            "applied from green tip through petal fall, following the local label",
            "Alternate fungicide mode-of-action groups to slow resistance",
        ],
    ),
    _entry(
        "Apple___Black_rot",
        "Apple",
        "Black rot / frogeye leaf spot (Botryosphaeria obtusa)",
        severity="moderate",
        symptoms=[
            "Small purple flecks on leaves that enlarge into round spots with purple margins and tan centres",
            "Sunken, reddish-brown cankers on branches and limbs",
            "Fruit develop firm brown rot with concentric rings of black fruiting bodies",
        ],
        prevention=[
            "Prune out dead wood, cankers and mummified fruit each season",
            "Remove fire-blight strikes promptly during the growing season",
            "Avoid bark wounds and disinfect cutting tools between trees",
        ],
        treatment=[
            "Sanitation is the main control measure for black rot",
            "Protective fungicides such as captan or myclobutanil during the spring infection window",
        ],
    ),
    _entry(
        "Apple___Cedar_apple_rust",
        "Apple",
        "Cedar apple rust (Gymnosporangium juniperi-virginianae)",
        severity="low",
        symptoms=[
            "Bright yellow-orange circular spots on the upper leaf surface with tiny black dots",
            "Tube-like structures develop on the underside of the leaf a few weeks later",
            "Orange galls may be visible on nearby juniper hosts",
        ],
        prevention=[
            "Remove juniper and cedar within roughly 1-2 km of the orchard where practical",
            "Select rust-resistant cultivars",
            "Maintain good airflow so leaves dry quickly after dew and rain",
        ],
        treatment=[
            "Fungicides such as myclobutanil or mancozeb from pink bud through petal fall, per label",
            "Timing matters: the spray window is short and driven by spore release",
        ],
    ),
    _entry(
        "Apple___healthy",
        "Apple",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # ------------------------------------------------------------ Blueberry
    _entry(
        "Blueberry___healthy",
        "Blueberry",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # --------------------------------------------------------------- Cherry
    _entry(
        "Cherry_(including_sour)___Powdery_mildew",
        "Cherry",
        "Powdery mildew (Podosphaera clandestina)",
        severity="moderate",
        symptoms=[
            "White powdery fungal growth on leaves, shoots and fruit surfaces",
            "Leaves curl upward and become distorted",
            "Fruit develop white colonies that may lead to cracking and deformation",
        ],
        prevention=[
            "Prune for open canopies that dry quickly",
            "Avoid excessive nitrogen, which promotes dense succulent growth",
            "Remove and destroy infected prunings",
        ],
        treatment=[
            "Sulfur or horticultural oil formulations applied early in the season where permitted",
            "DMI fungicides such as myclobutanil for longer-lasting control, alternating groups",
        ],
    ),
    _entry(
        "Cherry_(including_sour)___healthy",
        "Cherry",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # ----------------------------------------------------------------- Corn
    _entry(
        "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
        "Corn",
        "Gray leaf spot (Cercospora zeae-maydis)",
        severity="high",
        symptoms=[
            "Narrow, rectangular tan-to-grey lesions restricted by the leaf veins",
            "Lesions are sharply rectangular with dark borders on the upper leaf surface",
            "Severe infection causes the lower canopy to die and ears to lose weight",
        ],
        prevention=[
            "Plant hybrids with good gray leaf spot resistance",
            "Rotate corn with a non-host crop and manage surface residue",
            "Maintain balanced nitrogen and potassium nutrition",
            "Avoid continuous corn in the same field year after year",
        ],
        treatment=[
            "Foliar fungicides at early disease onset - triazole or strobilurin products, per label",
            "Base the decision on field risk, hybrid susceptibility and the forecast",
        ],
    ),
    _entry(
        "Corn_(maize)___Common_rust_",
        "Corn",
        "Common rust (Puccinia sorghi)",
        severity="moderate",
        symptoms=[
            "Small, cinnamon-brown pustules scattered on both leaf surfaces",
            "Pustules are elongated on stalks and husks",
            "Heavy infection dries the leaves prematurely and stunts the plant",
        ],
        prevention=[
            "Use resistant hybrids - rust resistance is usually the most effective control",
            "Remove volunteer corn and alternate hosts such as wild grasses",
            "Reduce plant stress with balanced fertility",
        ],
        treatment=[
            "Foliar fungicides when pustules appear on the ear leaf and disease pressure is high",
            "Spray before the tassel and early silking stages for the best economic response",
        ],
    ),
    _entry(
        "Corn_(maize)___Northern_Leaf_Blight",
        "Corn",
        "Northern corn leaf blight (Exserohilum turcicum)",
        severity="high",
        symptoms=[
            "Cigar-shaped grey-green to tan lesions that are 3-15 cm long",
            "Lesions are not bounded by the veins and may reach the leaf margin",
            "Severe cases cause complete leaf blighting, stalk rot and ear infection",
        ],
        prevention=[
            "Choose hybrids with partial or full resistance to the prevailing race",
            "Rotate away from corn and manage crop residue",
            "Scout fields regularly from the whorl stage onwards",
        ],
        treatment=[
            "Foliar fungicide between VT and early reproductive stages when risk is high",
            "Use a resistant hybrids strategy together with a planned fungicide program",
        ],
    ),
    _entry(
        "Corn_(maize)___healthy",
        "Corn",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # ---------------------------------------------------------------- Grape
    _entry(
        "Grape___Black_rot",
        "Grape",
        "Black rot (Guignardia bidwellii)",
        severity="high",
        symptoms=[
            "Tan circular leaf lesions with dark brown borders and pepper-like black fruiting bodies",
            "Lesions often form along the leaf margins",
            "Berries develop a light brown soft rot, then shrivel into hard black mummies",
        ],
        prevention=[
            "Remove every mummified berry from the canopy and the ground - they carry overwintering spores",
            "Prune out infected canes and improve canopy airflow",
            "Start the season with clean, well-timed fungicide cover",
        ],
        treatment=[
            "Protectant and systemic fungicides (captan, mancozeb, myclobutanil) from early shoot growth",
            "Re-apply after every 7-10 days during the critical infection period, and after rain",
        ],
    ),
    _entry(
        "Grape___Esca_(Black_Measles)",
        "Grape",
        "Esca / black measles (Phaeomoniella and Phaeoacremonium complex)",
        severity="high",
        symptoms=[
            "Interveinal yellowing that turns necrotic, producing a tiger-stripe pattern",
            "Dark streaks or spotting on the shoots",
            "White spongy rot under the bark of older trunks and cordon wood",
        ],
        prevention=[
            "Prune out infected wood well below the visible symptoms and destroy it",
            "Protect large pruning wounds with wound sealant or biological trunk disease protectants",
            "Disinfect tools between vines",
        ],
        treatment=[
            "There is no curative treatment for trunk infections - removal and prevention are the focus",
            "Preventive trunk disease fungicides at pruning can slow new infections",
        ],
    ),
    _entry(
        "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
        "Grape",
        "Isariopsis leaf spot (Pseudocercospora vitis)",
        severity="moderate",
        symptoms=[
            "Dark brown angular lesions on the lower leaf surface, often with a yellow halo",
            "Spots enlarge and merge, causing premature defoliation",
            "Severe infection weakens the vines and reduces carbohydrate reserves",
        ],
        prevention=[
            "Improve canopy airflow through pruning and shoot thinning",
            "Remove infected leaf debris from the vineyard floor",
            "Avoid overhead irrigation and irrigate early in the day",
        ],
        treatment=[
            "Protective fungicides such as captan, mancozeb or copper during the growing season",
            "Begin applications at the first symptoms and repeat after wet weather",
        ],
    ),
    _entry(
        "Grape___healthy",
        "Grape",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # --------------------------------------------------------------- Orange
    _entry(
        "Orange___Haunglongbing_(Citrus_greening)",
        "Orange",
        "Huanglongbing / citrus greening (Candidatus Liberibacter)",
        severity="high",
        symptoms=[
            "Blotchy, mottled and asymmetric yellowing of the leaf - unlike the symmetric pattern of nutrient deficiency",
            "Leaves show corky veins and become brittle and upright",
            "Fruit are small, misshapen, lopsided, and can develop a bitter taste with uneven colour",
        ],
        prevention=[
            "Control Asian citrus psyllid, the vector that transmits the bacterium",
            "Use certified disease-free nursery stock and do not move citrus material between regions",
            "Remove diseased trees promptly to reduce inoculum",
            "Remove alternate host plants such as orange jasmine",
        ],
        treatment=[
            "There is currently no cure for huanglongbing",
            "Management focuses on psyllid control and the removal of infected trees",
        ],
    ),
    # ---------------------------------------------------------------- Peach
    _entry(
        "Peach___Bacterial_spot",
        "Peach",
        "Bacterial spot (Xanthomonas arboricola pv. pruni)",
        severity="moderate",
        symptoms=[
            "Small water-soaked lesions on leaves that turn purple-brown and may drop out, giving a shot-hole look",
            "Affected leaves yellow and fall prematurely",
            "Sunken, rough fruit lesions that crack during ripening",
        ],
        prevention=[
            "Plant resistant cultivars and certified disease-free nursery stock",
            "Apply dormant copper sprays after leaf fall and before bud break",
            "Avoid overhead irrigation and provide windbreaks where possible",
        ],
        treatment=[
            "Fixed-copper bactericides, sometimes tank-mixed with oxytetracycline, from shuck split through petal fall",
            "Follow the local label, and rotate chemistry to limit resistance",
        ],
    ),
    _entry(
        "Peach___healthy",
        "Peach",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # ---------------------------------------------------------------- Pepper
    _entry(
        "Pepper,_bell___Bacterial_spot",
        "Pepper",
        "Bacterial spot (Xanthomonas spp.)",
        severity="moderate",
        symptoms=[
            "Small water-soaked circular spots on leaves that turn dark brown to black with yellow halos",
            "Spots can become angular as they are limited by the leaf veins",
            "Raised, rough, scabby spots appear on the fruit surface",
        ],
        prevention=[
            "Use certified pathogen-free seed and resistant varieties",
            "Rotate away from pepper and tomato for at least two seasons",
            "Avoid working in the field while foliage is wet",
            "Remove infected plant debris after harvest",
        ],
        treatment=[
            "Copper-based bactericides, often combined with mancozeb, applied preventatively",
            "Copper resistance is widespread, so rotate active ingredients and follow local guidance",
        ],
    ),
    _entry(
        "Pepper,_bell___healthy",
        "Pepper",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # --------------------------------------------------------------- Potato
    _entry(
        "Potato___Early_blight",
        "Potato",
        "Early blight (Alternaria solani)",
        severity="moderate",
        symptoms=[
            "Dark brown lesions with concentric rings - a 'target board' pattern - on older leaves",
            "Affected leaves yellow, dry out and die from the margins inwards",
            "Tubers may develop sunken, dark, leathery lesions",
        ],
        prevention=[
            "Rotate with non-solanaceous crops for at least two to three years",
            "Remove volunteer plants and crop debris that carry the fungus over winter",
            "Maintain balanced nutrition, particularly nitrogen and potassium",
            "Irrigate early in the day and avoid wetting the foliage",
        ],
        treatment=[
            "Protectant fungicides such as chlorothalonil or mancozeb, or QoI products such as azoxystrobin",
            "Begin applications at the first symptoms and rotate mode-of-action groups",
        ],
    ),
    _entry(
        "Potato___Late_blight",
        "Potato",
        "Late blight (Phytophthora infestans)",
        severity="critical",
        symptoms=[
            "Water-soaked, dark green to brown irregular lesions on leaves and stems",
            "A white, downy fungal growth appears on the underside of leaves in humid conditions",
            "Tubers develop a firm brown rot with a reddish granular margin; the flesh may turn brown",
        ],
        prevention=[
            "Plant certified disease-free seed potatoes and destroy cull piles and volunteers",
            "Monitor local blight forecasts and inspect fields at least weekly",
            "Avoid dense canopies and improve field drainage",
            "Destroy infected plants and volunteers promptly to reduce inoculum",
        ],
        treatment=[
            "Protectant and systemic fungicides (for example mandipropamid, cyazofamid, "
            "oxathiapiprolin or metalaxyl mixtures) - rotate FRAC groups to slow resistance",
            "Protectant sprays are more effective than eradicant sprays: act before infection",
        ],
    ),
    _entry(
        "Potato___healthy",
        "Potato",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # ------------------------------------------------------------- Raspberry
    _entry(
        "Raspberry___healthy",
        "Raspberry",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # --------------------------------------------------------------- Soybean
    _entry(
        "Soybean___healthy",
        "Soybean",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # ---------------------------------------------------------------- Squash
    _entry(
        "Squash___Powdery_mildew",
        "Squash",
        "Powdery mildew (Podosphaera xanthii)",
        severity="moderate",
        symptoms=[
            "White, talc-like powdery colonies on the upper and lower leaf surfaces",
            "Infected leaves yellow, curl and die prematurely",
            "Fruit stems and petioles can also be colonised, reducing yield and quality",
        ],
        prevention=[
            "Use powdery-mildew-resistant varieties where available",
            "Space plants for airflow and remove infected residues after harvest",
            "Avoid excess nitrogen and keep plants stress-free",
        ],
        treatment=[
            "Sulfur or horticultural oils at the first sign of disease where permitted",
            "Systemic fungicides such as myclobutanil or chlorothalonil for established infections",
            "Reapply after rain because most contact products are washed off",
        ],
    ),
    # ------------------------------------------------------------ Strawberry
    _entry(
        "Strawberry___Leaf_scorch",
        "Strawberry",
        "Leaf scorch (Diplocarpon earlianum)",
        severity="moderate",
        symptoms=[
            "Numerous small dark purple spots on the upper leaf surface that merge into larger purple-brown blotches",
            "The centre of the blotch usually stays purplish rather than turning brown",
            "Leaf margins curl and dry; runners and petioles may develop purple lesions",
        ],
        prevention=[
            "Renovate beds promptly after harvest and mow away old foliage",
            "Use resistant cultivars and plant with enough spacing for airflow",
            "Avoid overhead irrigation and use drip or soaker systems",
        ],
        treatment=[
            "Protectant fungicides such as captan or myclobutanil when symptoms appear",
            "Repeat applications at the recommended interval through the season",
        ],
    ),
    _entry(
        "Strawberry___healthy",
        "Strawberry",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
    # --------------------------------------------------------------- Tomato
    _entry(
        "Tomato___Bacterial_spot",
        "Tomato",
        "Bacterial spot (Xanthomonas spp.)",
        severity="moderate",
        symptoms=[
            "Small, water-soaked circular spots that turn dark brown to black with yellow halos",
            "Spots may become angular because they are bounded by leaf veins",
            "Greasy, scabby raised spots on green fruit",
        ],
        prevention=[
            "Use certified pathogen-free seed and transplants, and treat seed where permitted",
            "Rotate out of solanaceous crops and remove crop debris after harvest",
            "Avoid overhead irrigation and do not handle wet plants",
            "Control volunteer tomato and pepper plants",
        ],
        treatment=[
            "Copper bactericides, sometimes combined with mancozeb, applied preventatively",
            "Copper resistance is common, so alternate active ingredients and follow local guidance",
        ],
    ),
    _entry(
        "Tomato___Early_blight",
        "Tomato",
        "Early blight (Alternaria solani)",
        severity="moderate",
        symptoms=[
            "Brown lesions with concentric rings forming a target pattern on the lowest leaves",
            "Yellowing around the lesions, followed by leaf drop from the bottom up",
            "Dark, sunken lesions on stems and on the shoulder of the fruit near the stem",
        ],
        prevention=[
            "Rotate with non-solanaceous crops and remove infected debris",
            "Stake and prune plants, and mulch the soil to prevent splash",
            "Maintain balanced fertility and avoid plant stress",
            "Irrigate at the base early in the day",
        ],
        treatment=[
            "Protectant fungicides such as chlorothalonil or mancozeb, or QoI products such as azoxystrobin",
            "Rotate fungicide groups and follow the local label and pre-harvest interval",
        ],
    ),
    _entry(
        "Tomato___Leaf_Mold",
        "Tomato",
        "Leaf mould (Passalora fulva)",
        severity="moderate",
        symptoms=[
            "Pale yellow or olive blotches on the upper leaf surface with no sharp margin",
            "Olive-green to grey velvety mould on the underside of the leaf, centred on the blotches",
            "Leaves curl, wither and drop; the disease thrives in warm, humid, poorly ventilated conditions",
        ],
        prevention=[
            "Manage humidity - ventilate greenhouses and avoid overhead irrigation",
            "Space and prune plants so foliage dries quickly",
            "Use resistant varieties with the L1, L2 or L3 genes",
        ],
        treatment=[
            "Remove and destroy affected leaves to lower inoculum",
            "Improve ventilation and humidity control first - the environment drives the disease",
            "Protectant fungicides labelled for tomato leaf mould where permitted",
        ],
    ),
    _entry(
        "Tomato___Late_blight",
        "Tomato",
        "Late blight (Phytophthora infestans)",
        severity="high",
        symptoms=[
            "Irregular, water-soaked, greasy-looking grey-green blotches on the leaves",
            "Under humid conditions a white downy fungal growth appears on the underside of the blotches",
            "The blotches darken to brown-black and the leaf shrivels, often within days",
            "Dark brown lesions on petioles and stems, and firm greasy brown patches on green fruit",
        ],
        prevention=[
            "Plant certified seed and disease-free transplants, and destroy volunteer tomato and potato plants",
            "Rotate away from tomato and potato for at least two seasons",
            "Keep foliage dry - irrigate at the base in the early morning and improve spacing and airflow",
            "Monitor closely during cool, wet spells, which are the conditions that trigger epidemics",
        ],
        treatment=[
            "Protectant fungicides such as chlorothalonil, mancozeb or copper applied preventatively before forecast risk periods",
            "Systemic and translaminar products such as metalaxyl or cyazofamid where locally registered",
            "Act quickly: remove and destroy infected plants and do not compost them",
            "Alternate mode-of-action groups to slow the development of resistance",
        ],
    ),
    _entry(
        "Tomato___Septoria_leaf_spot",
        "Tomato",
        "Septoria leaf spot (Septoria lycopersici)",
        severity="moderate",
        symptoms=[
            "Numerous small, circular spots with grey-white centres and dark brown margins",
            "Tiny black fruiting bodies are visible in the centre of the spots",
            "Starts on the lower leaves and can cause complete defoliation",
        ],
        prevention=[
            "Remove lower leaves and infected debris, and rotate with non-solanaceous crops",
            "Stake plants and mulch the soil to reduce splash",
            "Avoid overhead irrigation and water at the base early in the day",
        ],
        treatment=[
            "Protectant fungicides such as chlorothalonil, mancozeb or copper, applied at first symptoms",
            "Clean up fallen leaves at the end of the season to break the cycle",
        ],
    ),
    _entry(
        "Tomato___Spider_mites Two-spotted_spider_mite",
        "Tomato",
        "Two-spotted spider mite (Tetranychus urticae)",
        severity="moderate",
        symptoms=[
            "Fine pale stippling and speckling on the upper leaf surface",
            "Leaves develop a bronzed, dirty appearance and can drop prematurely",
            "Fine silk webbing is visible on the underside of leaves and on the fruit in heavy infestations",
        ],
        prevention=[
            "Reduce dust and plant stress, and avoid broad-spectrum insecticides that flare mite outbreaks",
            "Maintain predatory mites and other natural enemies",
            "Monitor the underside of leaves early in the season, especially in hot, dry weather",
        ],
        treatment=[
            "Acaricides such as abamectin, hexythiazox or spiromesifen, rotated by mode of action",
            "Horticultural oil or insecticidal soap for light infestations; never apply oil in hot sun",
        ],
    ),
    _entry(
        "Tomato___Target_Spot",
        "Tomato",
        "Target spot (Corynespora cassiicola)",
        severity="high",
        symptoms=[
            "Small brown lesions with concentric rings and light centres, giving a target-like appearance",
            "Lesions appear on leaves, stems, petioles and fruit",
            "Severe infection causes rapid defoliation and sunscald on exposed fruit",
        ],
        prevention=[
            "Rotate with non-solanaceous crops and remove infected residue",
            "Stake and prune plants and avoid excessive nitrogen",
            "Start with clean seed and transplants, and control volunteer solanaceous plants",
        ],
        treatment=[
            "Protectant and systemic fungicides such as chlorothalonil, mancozeb or azoxystrobin",
            "Rotate mode-of-action groups and follow local label instructions",
        ],
    ),
    _entry(
        "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
        "Tomato",
        "Tomato yellow leaf curl virus (TYLCV)",
        severity="critical",
        symptoms=[
            "Upward curling and cupping of the leaflets with yellowed leaf margins",
            "Severe stunting of the plant with greatly reduced fruit set",
            "Symptoms appear on newly grown leaves after the plants have been infected",
        ],
        prevention=[
            "Control the whitefly vector with reflective mulch, insect screens and yellow sticky traps",
            "Use resistant varieties carrying the TYLCV resistance genes",
            "Remove and destroy infected transplants, and control weed hosts such as field bindweed",
            "Use insect-proof nursery stock and do not handle plants with tobacco residue",
        ],
        treatment=[
            "There is no cure for viral infection - infected plants should be removed",
            "Focus on whitefly control to protect the remaining crop",
        ],
    ),
    _entry(
        "Tomato___Tomato_mosaic_virus",
        "Tomato",
        "Tomato mosaic virus (ToMV)",
        severity="high",
        symptoms=[
            "Mottled light and dark green mosaic patterning on the leaves",
            "Leaf distortion, narrowing and sometimes fern-leaf appearance",
            "Stunted growth and uneven fruit ripening with internal browning",
        ],
        prevention=[
            "Use certified virus-free seed and disinfect seed and trays",
            "Wash hands and tools, and avoid handling plants after using tobacco products",
            "Control weeds that act as reservoirs and remove infected plants",
        ],
        treatment=[
            "There is no curative treatment for a viral infection",
            "Remove infected plants and sanitise the growing area to limit spread",
        ],
    ),
    _entry(
        "Tomato___healthy",
        "Tomato",
        "Healthy",
        healthy=True,
        severity="none",
        symptoms=_HEALTHY_GENERIC["symptoms"],
        prevention=_HEALTHY_GENERIC["prevention"],
        treatment=_HEALTHY_GENERIC["treatment"],
    ),
]


def _normalise_key(value: str) -> str:
    """Reduce a class name to a comparable key.

    Different dataset mirrors encode the crop/disease separator differently
    (``Apple___Apple_scab`` vs ``Apple__Apple_scab``).  Stripping every
    non-alphanumeric character makes the two forms comparable.
    """
    return re.sub(r"[^a-z0-9]", "", value.lower())


_BY_KEY: dict[str, DiseaseEntry] = {_normalise_key(entry.class_name): entry for entry in CLASSES}

# Also index by the display friendly crop/disease pair so a label such as
# "Tomato___Early_Blight" resolves to the canonical entry.
_BY_PAIR: dict[str, DiseaseEntry] = {
    _normalise_key(f"{entry.crop}{entry.disease}"): entry for entry in CLASSES
}

CANONICAL_CLASS_NAMES: list[str] = [entry.class_name for entry in CLASSES]


def resolve_class(label: str | None) -> DiseaseEntry | None:
    """Resolve a raw model label to a knowledge-base entry.

    Returns ``None`` when the label is not part of the trained class set -
    callers must then produce an uncertainty response rather than guessing.
    """
    if not label:
        return None
    key = _normalise_key(label)
    if key in _BY_KEY:
        return _BY_KEY[key]
    if key in _BY_PAIR:
        return _BY_PAIR[key]
    # Fall back to a substring search - some mirrors reorder or pad names.
    for candidate_key, entry in _BY_KEY.items():
        if candidate_key and candidate_key in key:
            return entry
    return None


def get_entry(label: str | None) -> DiseaseEntry | None:
    """Alias for :func:`resolve_class` kept for readability at call sites."""
    return resolve_class(label)


def unknown_entry() -> dict[str, Any]:
    """Payload used when the model returns a class we have no information for."""
    return {
        "crop": None,
        "disease": None,
        "display_name": "Unrecognised class",
        "is_healthy": False,
        "symptoms": [],
        "prevention": [],
        "treatment": [],
        "severity": "unknown",
        "disclaimer": GENERAL_DISCLAIMER,
    }
