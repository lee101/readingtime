# coding=utf-8
import re

books = {
    'dive': {
        'cover_image_url': 'dive.jpg',
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
    },
    'alphabet': {
        'cover_image_url': 'abc.jpg',
        'name': 'alphabet',
        'pages': [
            {
                'text': 'A  B  C    D  E  F  G    H  I  J  K  L  M    N  O  P  Q    R  S  T  U    V  W  X  Y  Z'
            },
            {
                'text': 'a  b  c    d  e  f  g    h  i  j  k  l  m    n  o  p  q    r  s  t  u    v  w  x  y  z'
            },
            {
                'text': 'Sounds Chart: \n'
                        'A  E  I  O  U\n'
                        'aa ae ai ao au    '
                        'ba be bi bo bu\n'
                        'ca ce ci co cu    '
                        'da de di do du\n'
                        'ea ee ei eo eu    '
                        'fa fe fi fo fu\n'
                        'ga ge gi go gu    '
                        'ha he hi ho hu\n'
                        'ia ie ii io iu    '
                        'ja je ji jo ju\n'
                        'ka ke ki ko ku    '
                        'la le li lo lu\n'
                        'ma me mi mo mu    '
                        'na ne ni no nu\n'
                        'oa oe oi oo ou    '
                        'pa pe pi po pu\n'
                        'qa qe qi qo qu    '
                        'ra re ri ro ru\n'
                        'sa se si so su    '
                        'ta te ti to tu\n'
                        'ua ue ui uo uu    '
                        'va ve vi vo vu\n'
                        'wa we wi wo wu    '
                        'xa xe xi xo xu\n'
                        'ya ye yi yo yu    '
                        'za ze zi zo zu\n'
            },
        ]
    },
    'at-the-zoo': {
        'cover_image_url': 'at-the-zoo-cover-small.jpg',
        'name': 'at-the-zoo',
        'pages': [
            {
                'text': 'I like to look at the zebras.',
                'imagePath': 'zebra1.jpg',
            },
            {
                'text': 'I like to look at the bear.',
                'imagePath': 'bear2.jpg',
            },
            {
                'text': 'I like to look at the tiger.',
                'imagePath': 'tiger3.jpg',
            },
            {
                'text': 'I like to look at the monkeys.',
                'imagePath': 'monkey4.jpg',
            },
            {
                'text': 'I like to look at the crocodile.',
                'imagePath': 'crocodile5.jpg',
            },
            {
                'text': 'I like to look at the hippo.',
                'imagePath': 'hippo6.jpg',
            },
            {
                'text': 'I like to look at the lion.',
                'imagePath': 'lion7.jpg',
            },
            {
                'text': 'I like to look at the elephants.',
                'imagePath': 'elephant8.jpg',
            },
        ]
    },
    'wildlife-in-a-city-pond': {
        'cover_image_url': 'wildlife-in-a-city-pond-cover300x260.png',
        'name': 'wildlife-in-a-city-pond',
        'pages': [
            {
                'text': u"""Wildlife in a City Pond""",
                'imagePath': 'wildlife-in-a-city-pond-1.png',
            },

            {
                'text':
                    u"""It was dark outside and I could not see much
               from my window. I had just moved that
               evening into a new house in the city of Pune,
               in India. There was a deafening cacophony
               emerging from the dark, as if hundreds
               of badly tuned radios were crackling away!
               It was only in the morning that the mystery
               began to be solved. There, below my balcony,
               was a small pond in an abandoned quarry. I
               realized it must be inhabited by many of the
               animals that woke up only at night!""",
                'imagePath': 'wildlife-in-a-city-pond-2.png',
                'dark_color': True,
                'css': """top: 62px;
    position: absolute;
    left: 265px;"""
            },

            {
                'text': u"""Over the next year, I watched the pond undergo
            incredible transformations through the seasons.
            In summer, the area looked like a dry, lifeless
            barren depression. But come monsoon and life
            burst out like an orchestra, waiting for the
            conductor to give the signal!
            The first raindrops on the thirsty land gave off
            a lovely earthy smell. But they also did what
            no magician could do, turning the brown earth
            into an oasis of green and blue.""",
                'imagePath': 'wildlife-in-a-city-pond-3.png',
            },

            {
                'text': u"""Within a few days, blades of reeds were glistening
            silver in the sun. Plants that had seemed forlorn
            and dead suddenly stood proud and tall. The
            chocolate brown rods of the typha plant swayed
            in the wind, as cottony flowers from nearby
            trees drifted everywhere.""",
                'imagePath': 'wildlife-in-a-city-pond-4.png',
            },

            {
                'text': u"""Other creatures too joined in nature’s
            dance. Brilliant blue kingfishers waited
            patiently on branches, suddenly
            swooping down to catch a fish with
            a splash. Baya weaver birds and
            scaly-breasted munias picked on the
            reeds to carry off nesting material.""",
                'imagePath': 'wildlife-in-a-city-pond-5.png',
            },

            {
                'text': u"""On the slopes near the pond, a pair of lapwings
            scurried around. Were they protecting their ‘nest’,
            a small depression in the ground with eggs
            that looked just like the earth? I think so, because
            every time any person came anywhere near,
            they would burst into noisy flight with a high
            pitched call of ‘did-you-do-it, did-you-do-it’.""",
                'imagePath': 'wildlife-in-a-city-pond-6.png',
            },

            {
                'text': u"""In the water, I noticed some rocks glistening in the sun. But as my
            binoculars focused on them, I was shocked. They were turtles! And then I
            saw movement under the water: more flapshell turtles, swimming with only
            their head sticking out. Just a week back, the ground was barren. Where did
            the turtles come from? I learnt from a book that they slept under the
            ground during the dry summer, waiting for the pond to fill up again. In their
            honour I started calling it the Flapshell Pond!""",
                'imagePath': 'wildlife-in-a-city-pond-turtles7.png',
            },

            {
                'text': u"""Several birds walked around the turtles, who peacefully ignored them.
            The white-breasted waterhen walked with a deliberate gait, looking
            for food. A couple of pond herons skulked through the tall reeds, wary
            of possible danger from birds of prey. And as the monsoon progressed,
            a pair of spot-billed ducks would land on Flapshell Pond, hunt for snails
            and waterplants, then take off to other natural ‘restaurants’!""",
                'imagePath': 'wildlife-in-a-city-pond-ducks8.png',
            },

            {
                'text': u"""At times the air was full of flying insects: brilliant red dragonflies, butterflies
            of various hues, and delicate damselflies visible only at a close distance.
            Insect and bird calls in the day created a different monsoon symphony
            than that of the night.""",
                'imagePath': 'wildlife-in-a-city-pond-9.png',
            },

            {
                'text': u"""I thought that such a small pond could not
            have any mammal, but was I mistaken!
            I would often see shy mongooses
            come to the edge of the water, and
            once an entire family with three babies!""",
                'imagePath': 'wildlife-in-a-city-pond-butterflies10.png',
            },

            {
                'text': u"""And where there were mongooses, could the
            snakes be far behind? Indeed I was lucky enough to
            see chequered keelbacks, pretty water snakes,
            swimming between the reeds.""",
                'imagePath': 'wildlife-in-a-city-pond-11.png',
            },

            {
                'text': u"""But what caused the deafening noise in the night?
            Frogs and toads in their hundreds, croaking
            and singing away to attract their mates!
            They were joined by crickets that
            seemed to have built-in loudspeakers,
            clinging to the reed blades. Listening carefully,
            I soon learnt to appreciate this symphony
            with its own rhythms.""",
                'imagePath': 'wildlife-in-a-city-pond-12.png',
            },

            {
                'text': u"""The night-time symphony had occasional guest appearances: the spotted
            owlet, bobbing up and down comically as I shone my torch on it, and the
            Indian nightjar, aptly named for its rather harsh ‘chuk-chuk-chrrrrr’
            continuing almost through the night.""",
                'imagePath': 'wildlife-in-a-city-pond-13.png',
            },

            {
                'text': u"""One day I got the scare of my life! No, not from snakes, nor from herons
            with mean-looking beaks, but rather, from some people walking around
            Flapshell Pond, looking like they were surveying the area. I found out from
            my neighbours that they were planning to drain the wetland and make
            buildings on it! My heart sank. I could not let this happen. A friend and I
            mobilized the neighbourhood kids. We invited a couple of press reporters.
            The next day, the newspapers carried news of the children’s appeal. Other
            residents of the area also started calling up various officials to tell them to
            save the pond. Then a couple of environmental organizations joined in. We
            invited the city commissioner too. At first, he was not convinced, but when
            he experienced the monsoon magic, he realized it would be a shame to
            destroy the pond.""",
                'imagePath': 'wildlife-in-a-city-pond-14.png',
            },

            {
                'text': u"""Finally, all this did the trick.
            Flapshell Pond was declared off-limits
            to any construction! How lucky I was to
            have experienced monsoon’s magic!""",
                'imagePath': 'wildlife-in-a-city-pond-15.png',
            },

            {
                'text': u"""Here was a mini-sanctuary in the middle of a
            bustling city, with its multiple symphonies. Here,
            nature’s dance could continue, providing life to
            thousands of creatures big and small. Sometimes,
            magic is found in one’s own backyard!""",
                'imagePath': 'wildlife-in-a-city-pond-16.png',
            },

            {
                'text': u"""Save a Pond!
            Do you have a pond near your house? Have you observed the diversity of
            life in and around it? Is it threatened by construction or pollution? If it is,
            can you get together with your friends and parents and their friends, and
            tell everyone that you want it saved?
            And if people who want to build on it ask why you want it saved?
            A simple answer: because birds and insects and other animals also need a
            home to stay in!""",
                'imagePath': 'wildlife-in-a-city-pond-17.png',
            },

            {
                'text': u"""Would it not be wonderful if there were thousands of such city ponds, with
            wildlife of all kinds? You could join children and adults in various parts of
            the world, through your computer networks or even snail mail, sharing
            photos and stories of what you see there, and how you managed to save
            them!""",
                'imagePath': 'wildlife-in-a-city-pond-18.png',
            },

        ],
    },
    #     'bhabhloo-bear': {
    #         'cover_image_url': 'bhabhloo-bear-cover.jpg',
    #         'name': 'bhabhloo-bear',
    #         'pages': [
    #             {
    #                 'text': 'Bhabhloo Bear\'s Adventure',
    #                 'imagePath': 'zebra1.jpg',
    #             },
    #             {
    #                 'text': 'High up on the snowy mountains of the Himalayas lived the beautiful little Bhabhloo Bear. Bhabhloo Bear\'s fur was long, black and shiny, with not even one white hair on it. Bhabhloo was a very, very naughty bear, loved by everyone in the jungle, but most of all, by his mother. But he was really very naughty.',
    #                 'imagePath': 'bear2.jpg',
    #             },
    #             {
    #                 'text': u"""
    #                 From early morning to nightfall, Bhabhloo would jump and play
    # and run through the jungle and his mother would call after him,
    # “Bhabhloo, beta, don’t be so naughty.”
    # “Bhabhloo, sit for a little while, rest a bit…”
    # “Oh no, Bhabhloo, you’ll get hurt, beta, be careful!”
    # “Bhabhloo, it’s late now, it’s night time, go to sleep now, son…”
    # """,
    #                 'imagePath': 'tiger3.jpg',
    #             },
    #             {
    #                 'text': u"""From early morning to nightfall, Bhabhloo would jump and play
    # and run through the jungle and his mother would call after him,
    # “Bhabhloo, beta, don’t be so naughty.”
    # “Bhabhloo, sit for a little while, rest a bit…”
    # “Oh no, Bhabhloo, you’ll get hurt, beta, be careful!”
    # “Bhabhloo, it’s late now, it’s night time, go to sleep now, son…”""",
    #                 'imagePath': 'monkey4.jpg',
    #             },
    #             {
    #                 'text': u"""Ma would keep trying to control Bhabhloo, and full-of-beans Bhabhloo would think of new
    # things to do, not listening to a word his mother said.
    # This is a story about just such a night. Ma was very tired. Who could blame her? She had been
    # running after Bhabhloo and scolding him all over the jungle, all day long. But Bhabhloo was
    # still too excited to sleep. His mind buzzed with questions.
    # His mind buzzed with questions.
    # “Where does the sun sleep at night?”
    # “Who is the moon’s mother?”
    # “At night, when I am not sleepy, why is Ma sleepy?”
    # “Why?…Where?…When?…How?…
    # How?…When?…Where?…Why?… ”""",
    #                 'imagePath': 'crocodile5.jpg',
    #             },
    #             {
    #                 'text': u"""Bhabhloo’s head buzzed with all these questions till he was quite dizzy. He just could not lie
    # still any longer, so he quietly slipped out of the den and sat outside in the cool night air.
    # Strange sounds filled the night. The ki-kit-kit of crickets, the hwash-hwaaasshh of the wind in
    # the trees. The jungle was lit up brightly by the full moon that hung low. But still, questions
    # flitted in Bhabhloo’s head like restless butterflies""",
    #                 'imagePath': 'hippo6.jpg',
    #             },
    #             {
    #                 'text': u"""Actually, it had long been Bhabhloo’s dream to do something, anything that would make the whole world sit up
    # and notice him. Something, anything that would make bears, big and small, say, “Wow! Bhabhloo has made
    # Himalayan bears famous throughout the world!”
    # But how? What was that special something that would make a baby bear famous worldwide?""",
    #                 'imagePath': 'lion7.jpg',
    #             },
    #             {
    #                 'text': u"""Lost in thought, Bhabhloo’s eye fell on a tall deodar tree as it swayed in the night breeze.
    # Whenever the tree swayed one way, it looked as if the highest branches were touching the
    # moon.
    # Suddenly Bhabhloo had a most brilliant idea! His eyes shone,
    # his hair stood on end in excitement, and he felt like dancing!!!
    # But he knew that if he made a noise, his mother would wake up
    # and then he would be immediately packed off to his bed.
    # And if she found out what was in Bhabhloo’s head she would
    # get angry with him and his dream would remain incomplete…""",
    #                 'imagePath': 'elephant8.jpg',
    #             },
    #             {
    #                 'text': u"""Oh yes, you are probably thinking
    # what in the world could have got
    # into Bhabhloo’s head after seeing
    # the tree, that would make his
    # dreams of fame come true? Well, I
    # will tell you.
    # He had always been an expert at
    # climbing trees. Now he would just
    # climb up that tall deodar tree.
    # And then, when the wind made the
    # tree sway and touch the moon, he
    # would leap up in an instant and
    # jump… straight…
    # onto…THE MOON!""",
    #                 'imagePath': 'elephant8.jpg',
    #             },
    #         ]
    #     },
}

for key, value in books.iteritems():
    book = books[key]
    for page in book['pages']:
        page['words'] = re.split(ur'([- ,.;:\'!?"…”“]*\s+[- ,.;:\'!?"…”“]*)', page['text'])
