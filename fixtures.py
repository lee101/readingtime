import re

books = {
    'dive': {
        'name': 'dive',
        'pages': [
            {
                'imagePath': 'tropical-fish1.png',
                'text': 'Dive! '
            },
            {
                'imagePath': 'on-the-boat2.png',
                'text': 'Blue skies and calm waters -- a perfect day for diving! We set out in a little boat, hoping for a BIG adventure! '
            },
            {
                'imagePath': 'scuba-gear3.png',
                'text': 'When we reached the dive site, we carefully checked all our equipment and put on our fins and masks. '
            },
            {
                'imagePath': 'scuba4.png',
                'text': 'As soon as we were underwater, we were greeted by a school of yellow back fusiliers. '
            },
            {
                'imagePath': 'parrot-fish5.png',
                'text': 'There were so many different creatures to see around this large table coral: oriental sweetlips, parrot fish, batfish, and even a beautifully-patterned nudibranch. '
            },
            {
                'imagePath': 'fish6.png',
                'text': 'This trumpet fish changed colour to try and blend in with a school of yellow tang, but you can pick him out easily enough, can\'t you? '
            },
            {
                'imagePath': 'lionfish7.png',
                'text': 'It\'s a good thing we kept a safe distance from this lionfish. The spines on his back can be quite poisonous! '
            },
            {
                'imagePath': 'nemo-fish8.png',
                'text': 'These clownfish carefully guarded their sea anemone home, but finally agreed to let me take a few pictures. '
            },
            {
                'imagePath': 'moray-eel9.png',
                'text': 'We saw a honeycomb moray eel having its teeth cleaned by cleaner wrasses, and another pair even offered to give us a scrub! '
            },
            {
                'imagePath': 'hidden-octopus10.png',
                'text': 'There were trigger fish and sea urchins. We even saw a coral grouper and a reef octopus playing hide-and-seek. '
            },
            {
                'imagePath': 'octopus11.png',
                'text': 'The octopus won the game. They\'re masters of disguise. Pipe fish are great at disguise too. Can you spot the two ghost pipefish in this picture? '
            },
            {
                'imagePath': 'reef-shark12.png',
                'text': 'We came across a couple of white tip reef sharks resting near the bottom. They\'re pretty harmless, so we swam in for a closer look'
            },
            {
                'imagePath': 'turtle13.png',
                'text': 'We followed this hawksbill turtle for a while as he looked around the reef for a nice sea sponge to lunch on. '
            },
            {
                'imagePath': 'manta-ray14.png',
                'text': 'As we made our way back to the boat, we were thrilled to see a manta ray \'flying\' through the water with two remora fish in tow. '
            },
            {
                'imagePath': 'dugong15.png',
                'text': 'And just when we thought this dive couldn\'t possibly get any better, we sighted a dugong grazing on somesea grass. '
            },
            {
                'imagePath': 'diving-ended16.png',
                'text': 'What an incredible experience! I can\'t wait to go diving again! '
            },
            {
                'imagePath': 'corals17.png',
                'text': 'Corals are both plants and animals. '
                        'Thousands of little algae live inside corals, and give them energy to grow. '
                        'They have hard outer skeletons and grow into many different shapes. '
                        'Plankton is the main source of food for many sea creatures. '
                        'They are a mix of algae, bacteria, tiny animals, and the eggs and larvae of larger animals that float about with the ocean currents. '
                        'Feat her stars may look like plants, but they\'re really animals. They use their feather-like \'arms\' to catch and eat bits of floating plankton. ',
                'layout': 'column',
            },
            {
                'imagePath': 'fish18.png',
                'text': 'Parrot fish have strong teeth that form a parrot-like beak, which they use to scrape algae off hard coral. '
                        'Some species don\'t mind eating bits of coral as well, and they later poop out a fine sand that washes up on land to form beautiful white beaches. Clownfish and sea anemones live together and help each other. '
                        'The clownfish help the anemones by cleaning their tentacles and luring other fish for the anemone to eat. The anemones, in turn, allow the clownfish to hide among their poisonous tentacles without stinging them. '
                        'Cleaner wrasses are small fish that keep bigger fish clean by feeding on their parasites and dead skin. '
                        'The bigger fish recognise the wrasses by their colours and the dance-like way they move. ',
                'layout': 'column',
            },
            {
                'imagePath': 'reef19.png',
                'text': 'The reef octopus can hide by changing its colour and texture. ' +
                        'It makes its home in holes in the reef, or buries itself in the sand. '
                        'Ghost pipefish can be found in pairs, floating with their heads down and hidden among sea grass, corals or feather stars. '
                        'Like the reef octopus, they can change colour to blend in perfectly. '
                        'The white tip reef shark has a thin body, broad head, and white tips on its dorsal and tail fin. '
                        'They hunt at night, and sleep through most of the day. ',
                'layout': 'column',

            },
            {
                'imagePath': 'turtle-manta-ray20.png',
                'text': 'The hawksbill turtle has a flat body, a shell with jagged edges, and a sharp, curving mouth that looks like a hawk\'s beak. '
                        'Manta rays are huge fish with wing-like fins on the sides of their bodies. '
                        'These large fins help them swim gracefully through the water. '
                        'On some manta rays, the distance from one wing tip to the other can reach up to 23 feet! '
                        'The dugong is a vegetarian marine mammal. '
                        'Its favourite food is sea grass, which it is able to graze on with its specially-shaped snout. '
                        'Dugongs are also called sea cows. ',
                'layout': 'column',
            }
        ]
    }
}

for key, value in books.iteritems():
    book = books[key]
    for page in book['pages']:
        page['words'] = re.split(r'([- ,.;:\'!?"]*\s+[- ,.;:\'!?"]*)', page['text'])
